"""Config and options flows for BLE Scale."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from .const import (
    CONF_ADAPTER,
    CONF_AGE,
    CONF_ATHLETE,
    CONF_GENDER,
    CONF_HEIGHT,
    CONF_HEIGHT_FEET,
    CONF_HEIGHT_INCHES,
    DEFAULT_AGE,
    DEFAULT_ATHLETE,
    DEFAULT_GENDER,
    DEFAULT_HEIGHT,
    DOMAIN,
)
from .scales import ADAPTER_NAMES, DeviceInfo, resolve_adapter

CM_PER_INCH = 2.54
INCHES_PER_FOOT = 12


def _device_info(discovery: BluetoothServiceInfoBleak) -> DeviceInfo:
    return DeviceInfo(
        local_name=discovery.name or "",
        service_uuids=tuple(discovery.service_uuids),
    )


def _device_label(discovery: BluetoothServiceInfoBleak) -> str:
    name = discovery.name
    if name and name != discovery.address:
        return f"{name} ({discovery.address})"
    return discovery.address


def _height_to_feet_inches(height_cm: float) -> tuple[int, int]:
    """Convert stored centimeters to whole feet and inches for the form."""
    total_inches = round(height_cm / CM_PER_INCH)
    return divmod(total_inches, INCHES_PER_FOOT)


def _profile_input_to_storage(user_input: dict[str, Any]) -> dict[str, Any]:
    """Convert form values to the metric profile used by scale protocols."""
    profile = dict(user_input)
    feet = int(profile.pop(CONF_HEIGHT_FEET))
    inches = int(profile.pop(CONF_HEIGHT_INCHES))
    height_cm = (feet * INCHES_PER_FOOT + inches) * CM_PER_INCH
    if not 100 <= height_cm <= 250:
        raise vol.Invalid("Height must be between 100 and 250 cm")
    profile[CONF_HEIGHT] = round(height_cm, 1)
    profile[CONF_AGE] = int(profile[CONF_AGE])
    return profile


def _profile_schema(defaults: dict[str, Any]) -> vol.Schema:
    if CONF_HEIGHT_FEET in defaults and CONF_HEIGHT_INCHES in defaults:
        feet = int(defaults[CONF_HEIGHT_FEET])
        inches = int(defaults[CONF_HEIGHT_INCHES])
    else:
        feet, inches = _height_to_feet_inches(
            float(defaults.get(CONF_HEIGHT, DEFAULT_HEIGHT))
        )
    return vol.Schema(
        {
            vol.Required(
                CONF_HEIGHT_FEET, default=feet
            ): NumberSelector(
                NumberSelectorConfig(
                    min=3,
                    max=8,
                    step=1,
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_HEIGHT_INCHES, default=inches
            ): NumberSelector(
                NumberSelectorConfig(
                    min=0,
                    max=11,
                    step=1,
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_AGE, default=defaults.get(CONF_AGE, DEFAULT_AGE)
            ): NumberSelector(
                NumberSelectorConfig(
                    min=10,
                    max=120,
                    step=1,
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_GENDER,
                default=defaults.get(CONF_GENDER, DEFAULT_GENDER),
            ): vol.In({"male": "Male", "female": "Female"}),
            vol.Required(
                CONF_ATHLETE,
                default=defaults.get(CONF_ATHLETE, DEFAULT_ATHLETE),
            ): bool,
        }
    )


class BleScaleConfigFlow(ConfigFlow, domain=DOMAIN):
    """Configure one BLE scale and one user profile."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovery: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}
        self._address = ""
        self._adapter_key = ""
        self._title = ""

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle manifest-driven Bluetooth discovery."""
        if not discovery_info.connectable:
            return self.async_abort(reason="not_connectable")
        adapter = resolve_adapter(_device_info(discovery_info))
        if adapter is None:
            return self.async_abort(reason="unsupported_device")

        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._discovery = discovery_info
        self._address = discovery_info.address
        self._adapter_key = adapter.key
        self._title = discovery_info.name or adapter.name
        self.context["title_placeholders"] = {"name": self._title}
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm a discovered scale before collecting profile data."""
        if user_input is not None:
            return await self.async_step_profile()
        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={"name": self._title},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user select any currently visible connectable BLE device."""
        if user_input is not None:
            address = str(user_input[CONF_ADDRESS])
            discovery = self._discovered_devices.get(address)
            if discovery is None:
                return self.async_show_form(
                    step_id="user",
                    data_schema=self._device_schema(),
                    errors={"base": "device_not_found"},
                )

            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            self._address = address
            self._title = discovery.name or address
            self._discovery = discovery
            adapter = resolve_adapter(_device_info(discovery))
            if adapter is None:
                return await self.async_step_protocol()
            self._adapter_key = adapter.key
            return await self.async_step_profile()

        await bluetooth.async_request_active_scan(self.hass)
        current_addresses = self._async_current_ids(include_ignore=False)
        self._discovered_devices = {
            discovery.address: discovery
            for discovery in async_discovered_service_info(
                self.hass, connectable=True
            )
            if discovery.address not in current_addresses
        }
        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")
        return self.async_show_form(
            step_id="user", data_schema=self._device_schema()
        )

    async def async_step_protocol(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose a protocol when the device name is not recognized."""
        if user_input is not None:
            self._adapter_key = str(user_input[CONF_ADAPTER])
            return await self.async_step_profile()
        return self.async_show_form(
            step_id="protocol",
            data_schema=vol.Schema(
                {vol.Required(CONF_ADAPTER): vol.In(ADAPTER_NAMES)}
            ),
        )

    async def async_step_profile(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect the profile used for scale setup and calculations."""
        if user_input is not None:
            try:
                profile = _profile_input_to_storage(user_input)
            except vol.Invalid:
                return self.async_show_form(
                    step_id="profile",
                    data_schema=_profile_schema(user_input),
                    errors={"base": "invalid_height"},
                )
            return self.async_create_entry(
                title=self._title,
                data={
                    CONF_ADDRESS: self._address,
                    CONF_ADAPTER: self._adapter_key,
                    **profile,
                },
            )
        return self.async_show_form(
            step_id="profile", data_schema=_profile_schema({})
        )

    def _device_schema(self) -> vol.Schema:
        return vol.Schema(
            {
                vol.Required(CONF_ADDRESS): vol.In(
                    {
                        address: _device_label(discovery)
                        for address, discovery in self._discovered_devices.items()
                    }
                )
            }
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> BleScaleOptionsFlow:
        """Create the profile options flow."""
        return BleScaleOptionsFlow()


class BleScaleOptionsFlow(OptionsFlowWithReload):
    """Edit the profile for an existing scale entry."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show and save profile options."""
        if user_input is not None:
            try:
                profile = _profile_input_to_storage(user_input)
            except vol.Invalid:
                return self.async_show_form(
                    step_id="init",
                    data_schema=_profile_schema(user_input),
                    errors={"base": "invalid_height"},
                )
            return self.async_create_entry(title="", data=profile)
        defaults = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(
            step_id="init", data_schema=_profile_schema(defaults)
        )
