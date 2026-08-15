"""Inlife / FatScale protocol."""

from __future__ import annotations

from ..body_comp import build_payload, uuid16, xor_checksum
from ..models import BodyComposition, ScaleBodyComp, ScaleReading, UserProfile
from .base import (
    ConnectionContext,
    DeviceInfo,
    ScaleAdapter,
    profile_byte,
    uint16_be,
    uint32_be,
)


class InlifeScaleAdapter(ScaleAdapter):
    """Inlife and FatScale BLE body-fat scales."""

    key = "inlife"
    name = "Inlife"
    priority = 90
    exact_names = ("000fatscale01", "000fatscale02", "042fatscale01")
    service_uuids = ("fff0",)
    char_notify_uuid = uuid16(0xFFF1)
    char_write_uuid = uuid16(0xFFF2)

    def __init__(self) -> None:
        self._comp = ScaleBodyComp()
        self._impedance = 0.0

    def matches(self, device: DeviceInfo) -> bool:
        name = device.local_name.casefold()
        if name in self.exact_names:
            return True
        if name:
            return False
        if device.characteristic_uuids:
            chars = {
                value.casefold().replace("-", "")
                for value in device.characteristic_uuids
            }
            own_write = self.char_write_uuid.replace("-", "")
            one_byone_notify = uuid16(0xFFF4).replace("-", "")
            return own_write in chars and one_byone_notify not in chars
        return super().matches(device)

    async def on_connected(self, context: ConnectionContext) -> None:
        self._comp = ScaleBodyComp()
        self._impedance = 0.0
        profile = context.profile
        command = bytearray(
            [
                0x02,
                0xD2,
                0x01,
                0x00 if profile.gender == "male" else 0x01,
                0x01,
                profile_byte(profile.age),
                profile_byte(profile.height),
                0,
                0,
                0,
                0,
                0,
            ]
        )
        command.extend((xor_checksum(command), 0xAA))
        await context.write(self.char_write_uuid, bytes(command), response=False)

    def parse_notification(self, data: bytes) -> ScaleReading | None:
        if len(data) < 14 or data[0] != 0x02:
            return None
        weight = uint16_be(data, 2) / 10
        if weight <= 0:
            return None

        if data[11] in (0x80, 0x81):
            self._impedance = float(uint32_be(data, 4))
            self._comp = ScaleBodyComp()
        else:
            visceral = uint16_be(data, 7) / 10
            self._comp = ScaleBodyComp(
                visceral_fat=visceral if visceral > 0 else None
            )
            self._impedance = 0.0
        return ScaleReading(weight, self._impedance)

    def compute_metrics(
        self, reading: ScaleReading, profile: UserProfile
    ) -> BodyComposition:
        return build_payload(reading.weight, reading.impedance, self._comp, profile)
