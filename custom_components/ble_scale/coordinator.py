"""Bluetooth session manager for BLE Scale."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import UTC, datetime
import logging
from time import monotonic
from typing import Any

from bleak_retry_connector import (
    BLEAK_RETRY_EXCEPTIONS,
    BleakClientWithServiceCache,
    establish_connection,
)

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    BluetoothChange,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_ADAPTER,
    CONF_AGE,
    CONF_ATHLETE,
    CONF_GENDER,
    CONF_HEIGHT,
    CONNECT_TIMEOUT,
    MEASUREMENT_TIMEOUT,
    RECONNECT_COOLDOWN,
)
from .models import ScaleMeasurement, ScaleReading, UserProfile
from .scales import adapter_for_key
from .scales.base import ConnectionContext, ScaleAdapter

_LOGGER = logging.getLogger(__name__)


class _BleakConnectionContext(ConnectionContext):
    """Expose only the GATT operations needed by protocol adapters."""

    def __init__(
        self, client: BleakClientWithServiceCache, profile: UserProfile
    ) -> None:
        self._client = client
        self.profile = profile

    async def write(
        self, char_uuid: str, data: bytes, response: bool = False
    ) -> None:
        await self._client.write_gatt_char(
            char_uuid, data, response=response
        )


class BleScaleCoordinator(DataUpdateCoordinator[ScaleMeasurement]):
    """Connect to a scale when it advertises and publish completed readings."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"BLE Scale {entry.unique_id}",
        )
        self.entry = entry
        self.address = str(entry.data["address"])
        self.adapter: ScaleAdapter = adapter_for_key(
            str(entry.data[CONF_ADAPTER])
        )
        profile_data = {**entry.data, **entry.options}
        self.profile = UserProfile(
            height=float(profile_data[CONF_HEIGHT]),
            age=int(profile_data[CONF_AGE]),
            gender=profile_data[CONF_GENDER],
            is_athlete=bool(profile_data[CONF_ATHLETE]),
        )
        self._cancel_bluetooth_callback: Any = None
        self._connect_task: asyncio.Task[None] | None = None
        self._cooldown_until = 0.0

    async def async_start(self) -> None:
        """Start listening for advertisements from this scale."""
        self._cancel_bluetooth_callback = bluetooth.async_register_callback(
            self.hass,
            self._async_advertisement,
            {"address": self.address, "connectable": True},
            BluetoothScanningMode.ACTIVE,
        )

    async def async_shutdown(self) -> None:
        """Stop advertisement listening and any active GATT session."""
        if self._cancel_bluetooth_callback is not None:
            self._cancel_bluetooth_callback()
            self._cancel_bluetooth_callback = None
        if self._connect_task is not None:
            self._connect_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._connect_task
            self._connect_task = None

    @callback
    def _async_advertisement(
        self,
        service_info: BluetoothServiceInfoBleak,
        change: BluetoothChange,
    ) -> None:
        """Schedule a connection when the configured scale is visible."""
        del service_info, change
        if self._connect_task is not None or monotonic() < self._cooldown_until:
            return
        self._connect_task = self.hass.async_create_task(
            self._async_collect_measurement(),
            f"BLE Scale measurement {self.address}",
        )

    async def _async_collect_measurement(self) -> None:
        """Run one connect, initialize, notify, and disconnect session."""
        succeeded = False
        client: BleakClientWithServiceCache | None = None
        unlock_task: asyncio.Task[None] | None = None
        hold_handle: asyncio.TimerHandle | None = None
        done = asyncio.Event()
        latest_reading: ScaleReading | None = None

        @callback
        def notification_handler(_sender: Any, data: bytearray) -> None:
            nonlocal latest_reading, hold_handle
            try:
                reading = self.adapter.parse_notification(bytes(data))
            except (IndexError, ValueError):
                _LOGGER.debug(
                    "Discarding malformed notification from %s",
                    self.address,
                    exc_info=True,
                )
                return
            if reading is None or not self.adapter.is_complete(reading):
                return
            latest_reading = reading
            if (
                self.adapter.completion_hold <= 0
                or self.adapter.is_final(reading)
            ):
                done.set()
                return
            if hold_handle is None:
                hold_handle = self.hass.loop.call_later(
                    self.adapter.completion_hold, done.set
                )

        try:
            ble_device = bluetooth.async_ble_device_from_address(
                self.hass, self.address, connectable=True
            )
            if ble_device is None:
                return

            async with asyncio.timeout(CONNECT_TIMEOUT):
                client = await establish_connection(
                    BleakClientWithServiceCache,
                    ble_device,
                    ble_device.name or self.entry.title,
                    max_attempts=3,
                )

            await client.start_notify(
                self.adapter.char_notify_uuid, notification_handler
            )
            context = _BleakConnectionContext(client, self.profile)
            await self.adapter.on_connected(context)

            if self.adapter.unlock_command is not None:
                await context.write(
                    self.adapter.char_write_uuid,
                    self.adapter.unlock_command,
                    response=False,
                )
                if self.adapter.unlock_interval > 0:
                    unlock_task = self.hass.async_create_task(
                        self._periodic_unlock(context),
                        f"BLE Scale unlock {self.address}",
                    )

            async with asyncio.timeout(MEASUREMENT_TIMEOUT):
                await done.wait()
            if latest_reading is None:
                return

            measurement = ScaleMeasurement(
                body=self.adapter.compute_metrics(
                    latest_reading, self.profile
                ),
                measured_at=datetime.now(UTC),
            )
            self.async_set_updated_data(measurement)
            succeeded = True
        except TimeoutError:
            _LOGGER.debug("Timed out reading BLE scale %s", self.address)
        except BLEAK_RETRY_EXCEPTIONS:
            _LOGGER.debug(
                "Bluetooth error reading scale %s",
                self.address,
                exc_info=True,
            )
        finally:
            if hold_handle is not None:
                hold_handle.cancel()
            if unlock_task is not None:
                unlock_task.cancel()
                with suppress(asyncio.CancelledError):
                    await unlock_task
            if client is not None and client.is_connected:
                with suppress(*BLEAK_RETRY_EXCEPTIONS):
                    await client.disconnect()
            self._cooldown_until = monotonic() + (
                RECONNECT_COOLDOWN if succeeded else 5.0
            )
            self._connect_task = None

    async def _periodic_unlock(
        self, context: _BleakConnectionContext
    ) -> None:
        """Repeat protocols that require a periodic keepalive/unlock."""
        assert self.adapter.unlock_command is not None
        while True:
            await asyncio.sleep(self.adapter.unlock_interval)
            try:
                await context.write(
                    self.adapter.char_write_uuid,
                    self.adapter.unlock_command,
                    response=False,
                )
            except BLEAK_RETRY_EXCEPTIONS:
                return
