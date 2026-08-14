"""Senssun Fat Scale protocol."""

from __future__ import annotations

from ..body_comp import build_payload, uuid16, xor_checksum
from ..models import BodyComposition, ScaleBodyComp, ScaleReading, UserProfile
from .base import ConnectionContext, ScaleAdapter, uint16_be

FRAME_WEIGHT = 0x01
FRAME_FAT = 0x02
FRAME_MUSCLE = 0x04
FRAME_BMR = 0x08
FRAME_ALL = FRAME_WEIGHT | FRAME_FAT | FRAME_MUSCLE | FRAME_BMR

_UNLOCK_PREFIX = bytes([0xA5, 0x10, 0x11, 0x1E, 0xA0, 0x00, 0x00])


class SenssunAdapter(ScaleAdapter):
    """Senssun Fat Scale."""

    key = "senssun"
    name = "Senssun Fat Scale"
    priority = 260
    exact_names = ("senssun fat",)
    char_notify_uuid = uuid16(0xFFF1)
    char_write_uuid = uuid16(0xFFF2)
    unlock_command = _UNLOCK_PREFIX + bytes(
        [xor_checksum(_UNLOCK_PREFIX[1:7]), 0x00]
    )
    unlock_interval = 5.0

    def __init__(self) -> None:
        self._weight = 0.0
        self._fat = 0.0
        self._water = 0.0
        self._muscle = 0.0
        self._bone = 0.0
        self._frames = 0

    async def on_connected(self, context: ConnectionContext) -> None:
        self._weight = 0.0
        self._fat = 0.0
        self._water = 0.0
        self._muscle = 0.0
        self._bone = 0.0
        self._frames = 0

    def parse_notification(self, data: bytes) -> ScaleReading | None:
        frame = data.lstrip(b"\xff")
        if len(frame) < 3:
            return None

        frame_type = frame[0]
        if frame_type == 0xA5 and len(frame) >= 6:
            self._weight = uint16_be(frame, 1) / 10
            self._frames |= FRAME_WEIGHT
        elif frame_type == 0xB0 and len(frame) >= 5:
            self._fat = uint16_be(frame, 1) / 10
            self._water = uint16_be(frame, 3) / 10
            self._frames |= FRAME_FAT
        elif frame_type == 0xC0 and len(frame) >= 5:
            self._muscle = uint16_be(frame, 1) / 10
            self._bone = uint16_be(frame, 3) / 10
            self._frames |= FRAME_MUSCLE
        elif frame_type == 0xD0:
            self._frames |= FRAME_BMR

        if self._weight <= 0:
            return None
        return ScaleReading(self._weight)

    def is_complete(self, reading: ScaleReading) -> bool:
        return reading.weight > 0 and self._frames & FRAME_ALL == FRAME_ALL

    def compute_metrics(
        self, reading: ScaleReading, profile: UserProfile
    ) -> BodyComposition:
        comp = ScaleBodyComp(
            fat=self._fat if self._fat > 0 else None,
            water=self._water if self._water > 0 else None,
            muscle=self._muscle if self._muscle > 0 else None,
            bone=self._bone if self._bone > 0 else None,
        )
        return build_payload(reading.weight, reading.impedance, comp, profile)
