"""Hoffen BS-8107 scale protocol."""

from __future__ import annotations

from ..body_comp import build_payload, uuid16, xor_checksum
from ..models import BodyComposition, ScaleBodyComp, ScaleReading, UserProfile
from .base import ConnectionContext, ScaleAdapter, profile_byte, uint16_le


class HoffenAdapter(ScaleAdapter):
    """Hoffen BS-8107 BLE body-fat scale."""

    key = "hoffen"
    name = "Hoffen BS-8107"
    priority = 20
    exact_names = ("hoffen bs-8107",)
    char_notify_uuid = uuid16(0xFFB2)
    char_write_uuid = uuid16(0xFFB2)

    def __init__(self) -> None:
        self._comp = ScaleBodyComp()

    async def on_connected(self, context: ConnectionContext) -> None:
        self._comp = ScaleBodyComp()
        profile = context.profile
        command = bytearray(
            [
                0xFA,
                0x85,
                0x03,
                0x00 if profile.gender == "male" else 0x01,
                profile_byte(profile.age),
                profile_byte(profile.height),
            ]
        )
        command.append(xor_checksum(command))
        await context.write(self.char_write_uuid, bytes(command), response=False)

    def parse_notification(self, data: bytes) -> ScaleReading | None:
        if len(data) < 5 or data[0] != 0xFA:
            return None
        weight = uint16_le(data, 3) / 10
        if len(data) >= 19 and data[5] == 0:
            fat = uint16_le(data, 6) / 10
            water = uint16_le(data, 8) / 10
            muscle = uint16_le(data, 10) / 10
            bone = data[14] / 10
            visceral = uint16_le(data, 17) / 10
            self._comp = ScaleBodyComp(
                fat=fat if fat > 0 else None,
                water=water if water > 0 else None,
                muscle=muscle if muscle > 0 else None,
                bone=bone if bone > 0 else None,
                visceral_fat=visceral if visceral > 0 else None,
            )
        return ScaleReading(weight)

    def compute_metrics(
        self, reading: ScaleReading, profile: UserProfile
    ) -> BodyComposition:
        return build_payload(reading.weight, reading.impedance, self._comp, profile)
