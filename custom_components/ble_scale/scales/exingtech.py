"""Exingtech Y1 scale protocol."""

from __future__ import annotations

from ..body_comp import build_payload
from ..models import BodyComposition, ScaleBodyComp, ScaleReading, UserProfile
from .base import ConnectionContext, ScaleAdapter, profile_byte, uint16_be


class ExingtechY1Adapter(ScaleAdapter):
    """Exingtech Y1 / vscale BLE body-fat scale."""

    key = "exingtech_y1"
    name = "Exingtech Y1"
    priority = 120
    exact_names = ("vscale",)
    service_uuids = ("f433bd80-75b8-11e2-97d9-0002a5d5c51b",)
    char_notify_uuid = "1a2ea400-75b9-11e2-be05-0002a5d5c51b"
    char_write_uuid = "29f11080-75b9-11e2-8bf6-0002a5d5c51b"

    def __init__(self) -> None:
        self._comp = ScaleBodyComp()

    async def on_connected(self, context: ConnectionContext) -> None:
        self._comp = ScaleBodyComp()
        profile = context.profile
        await context.write(
            self.char_write_uuid,
            bytes(
                [
                    0x10,
                    0x01,
                    0x00 if profile.gender == "male" else 0x01,
                    profile_byte(profile.age),
                    profile_byte(profile.height),
                ]
            ),
            response=False,
        )

    def parse_notification(self, data: bytes) -> ScaleReading | None:
        if len(data) < 15:
            return None
        weight = uint16_be(data, 4) / 10
        if weight <= 0:
            return None

        complete = data[6] != 0xFF
        self._comp = ScaleBodyComp(
            fat=uint16_be(data, 6) / 10 if complete else None,
            water=uint16_be(data, 8) / 10 if complete else None,
            bone=uint16_be(data, 10) / 10 if complete else None,
            muscle=uint16_be(data, 12) / 10 if complete else None,
            visceral_fat=float(data[14]) if complete else None,
        )
        return ScaleReading(weight)

    def is_complete(self, reading: ScaleReading) -> bool:
        return (
            reading.weight > 0
            and self._comp.fat is not None
            and self._comp.fat > 0
        )

    def compute_metrics(
        self, reading: ScaleReading, profile: UserProfile
    ) -> BodyComposition:
        return build_payload(reading.weight, reading.impedance, self._comp, profile)
