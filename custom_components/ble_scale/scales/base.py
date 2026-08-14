"""Common scale-adapter interfaces and helpers.

This package contains modified Python ports of GPL-3.0-licensed
ble-scale-sync scale adapters, copyright (C) 2026 Kristián Partl.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import floor
from typing import Protocol

from ..body_comp import build_payload
from ..models import BodyComposition, ScaleBodyComp, ScaleReading, UserProfile


@dataclass(frozen=True, slots=True)
class DeviceInfo:
    """Bluetooth information used to select a scale protocol."""

    local_name: str
    service_uuids: tuple[str, ...] = ()
    characteristic_uuids: tuple[str, ...] = ()


class ConnectionContext(Protocol):
    """Operations available to an adapter after a GATT connection."""

    profile: UserProfile

    async def write(
        self, char_uuid: str, data: bytes, response: bool = False
    ) -> None:
        """Write a characteristic."""


class ScaleAdapter:
    """Base class for a connectable scale protocol."""

    key = ""
    name = ""
    priority = 0
    exact_names: tuple[str, ...] = ()
    included_names: tuple[str, ...] = ()
    service_uuids: tuple[str, ...] = ()
    char_notify_uuid = ""
    char_write_uuid = ""
    unlock_command: bytes | None = None
    unlock_interval = 0.0
    completion_hold = 0.0

    def matches(self, device: DeviceInfo) -> bool:
        """Return whether this adapter claims a device."""
        name = device.local_name.casefold()
        if name and name in self.exact_names:
            return True
        if name and any(token in name for token in self.included_names):
            return True
        device_services = {_normalize_uuid(value) for value in device.service_uuids}
        return any(
            _normalize_uuid(value) in device_services
            for value in self.service_uuids
        )

    async def on_connected(self, context: ConnectionContext) -> None:
        """Initialize the scale after notification subscription."""

    def parse_notification(self, data: bytes) -> ScaleReading | None:
        """Decode one notification frame."""
        raise NotImplementedError

    def is_complete(self, reading: ScaleReading) -> bool:
        """Return whether enough data has arrived to publish."""
        return reading.weight > 0

    def is_final(self, reading: ScaleReading) -> bool:
        """Return whether a hold-open session may end immediately."""
        return True

    def compute_metrics(
        self, reading: ScaleReading, profile: UserProfile
    ) -> BodyComposition:
        """Build measured and derived metrics."""
        return build_payload(reading.weight, reading.impedance, ScaleBodyComp(), profile)


def uint16_be(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 2], "big")


def uint16_le(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 2], "little")


def uint32_be(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 4], "big")


def profile_byte(value: float | int) -> int:
    return min(0xFF, max(0, floor(value + 0.5)))


def _normalize_uuid(value: str) -> str:
    normalized = value.casefold().replace("-", "")
    suffix = "00001000800000805f9b34fb"
    if (
        len(normalized) == 32
        and normalized.startswith("0000")
        and normalized.endswith(suffix)
    ):
        return normalized[4:8]
    return normalized
