"""Hesley / YunChen scale protocol."""

from __future__ import annotations

from ..body_comp import build_payload, uuid16
from ..models import BodyComposition, ScaleBodyComp, ScaleReading, UserProfile
from .base import ConnectionContext, ScaleAdapter, uint16_be


class HesleyScaleAdapter(ScaleAdapter):
    """Hesley / YunChen BLE body-fat scales."""

    key = "hesley"
    name = "Hesley / YunChen"
    priority = 100
    exact_names = ("yunchen",)
    char_notify_uuid = uuid16(0xFFF4)
    char_write_uuid = uuid16(0xFFF1)
    unlock_command = bytes([0xA5, 0x01, 0x2C, 0xAB, 0x50, 0x5A, 0x29])

    def __init__(self) -> None:
        self._comp = ScaleBodyComp()

    async def on_connected(self, context: ConnectionContext) -> None:
        self._comp = ScaleBodyComp()

    def parse_notification(self, data: bytes) -> ScaleReading | None:
        if len(data) < 14:
            return None
        weight = uint16_be(data, 2) / 100
        if weight <= 0:
            return None

        fat = uint16_be(data, 4) / 10
        water = uint16_be(data, 8) / 10
        muscle = uint16_be(data, 10) / 10
        bone = uint16_be(data, 12) / 10
        self._comp = ScaleBodyComp(
            fat=fat if fat > 0 else None,
            water=water if water > 0 else None,
            muscle=muscle if muscle > 0 else None,
            bone=bone if bone > 0 else None,
        )
        return ScaleReading(weight)

    def compute_metrics(
        self, reading: ScaleReading, profile: UserProfile
    ) -> BodyComposition:
        return build_payload(reading.weight, reading.impedance, self._comp, profile)
