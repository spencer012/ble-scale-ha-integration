"""Digoo / Mengii scale protocol."""

from __future__ import annotations

from ..body_comp import build_payload, uuid16
from ..models import BodyComposition, ScaleBodyComp, ScaleReading, UserProfile
from .base import ConnectionContext, ScaleAdapter, profile_byte, uint16_be


class DigooScaleAdapter(ScaleAdapter):
    """Digoo / Mengii BLE body-fat scales."""

    key = "digoo"
    name = "Digoo / Mengii"
    priority = 80
    exact_names = ("mengii",)
    char_notify_uuid = uuid16(0xFFF1)
    char_write_uuid = uuid16(0xFFF2)

    def __init__(self) -> None:
        self._comp = ScaleBodyComp()
        self._stable = False
        self._all_values = False

    async def on_connected(self, context: ConnectionContext) -> None:
        self._comp = ScaleBodyComp()
        self._stable = False
        self._all_values = False
        profile = context.profile
        command = bytearray(
            [
                0x09,
                0x10,
                0x12,
                0x11,
                0x0D,
                0x01,
                profile_byte(profile.height),
                profile_byte(profile.age),
                0x00 if profile.gender == "male" else 0x01,
                0x01,
                0,
                0,
                0,
                0,
                0,
            ]
        )
        command.append(sum(command[3:15]) & 0xFF)
        await context.write(self.char_write_uuid, bytes(command), response=False)

    def parse_notification(self, data: bytes) -> ScaleReading | None:
        if len(data) < 19:
            return None
        weight = uint16_be(data, 3) / 100
        if weight <= 0:
            return None

        self._stable = bool(data[5] & 0x01)
        self._all_values = bool(data[5] & 0x02)
        if self._all_values:
            fat = uint16_be(data, 6) / 10
            visceral = data[10] / 10
            water = uint16_be(data, 11) / 10
            muscle = uint16_be(data, 16) / 10
            bone = data[18] / 10
            self._comp = ScaleBodyComp(
                fat=fat if fat > 0 else None,
                visceral_fat=visceral if visceral > 0 else None,
                water=water if water > 0 else None,
                muscle=muscle if muscle > 0 else None,
                bone=bone if bone > 0 else None,
            )
        else:
            self._comp = ScaleBodyComp()
        return ScaleReading(weight)

    def is_complete(self, reading: ScaleReading) -> bool:
        return reading.weight > 0 and self._stable and self._all_values

    def compute_metrics(
        self, reading: ScaleReading, profile: UserProfile
    ) -> BodyComposition:
        return build_payload(reading.weight, reading.impedance, self._comp, profile)
