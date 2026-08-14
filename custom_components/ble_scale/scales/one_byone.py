"""1byone scale protocols."""

from __future__ import annotations

from datetime import datetime

from ..body_comp import uuid16, xor_checksum
from ..models import ScaleReading
from .base import ConnectionContext, DeviceInfo, ScaleAdapter, uint16_le


class OneByoneAdapter(ScaleAdapter):
    """Eufy C1/P1/A1 and Health Scale branded 1byone devices."""

    key = "one_byone"
    name = "1byone (Eufy C1/P1)"
    priority = 70
    included_names = ("t9146", "t9147", "t9120", "health scale")
    char_notify_uuid = uuid16(0xFFF4)
    char_write_uuid = uuid16(0xFFF1)
    completion_hold = 3.0

    def __init__(self) -> None:
        self._previous_raw_weight: int | None = None
        self._weight_stable = False

    def matches(self, device: DeviceInfo) -> bool:
        if super().matches(device):
            return True
        chars = {
            value.casefold().replace("-", "") for value in device.characteristic_uuids
        }
        if not chars:
            return False
        notify = self.char_notify_uuid.replace("-", "")
        inlife_write = uuid16(0xFFF2).replace("-", "")
        return notify in chars and inlife_write not in chars

    async def on_connected(self, context: ConnectionContext) -> None:
        self._previous_raw_weight = None
        self._weight_stable = False

        unit_command = bytearray(
            [0xFD, 0x37, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        )
        unit_command.append(xor_checksum(unit_command))
        await context.write(self.char_write_uuid, bytes(unit_command), response=False)

        now = datetime.now()
        clock_command = bytes(
            [
                0xF1,
                (now.year >> 8) & 0xFF,
                now.year & 0xFF,
                now.month,
                now.day,
                now.hour,
                now.minute,
                now.second,
            ]
        )
        await context.write(self.char_write_uuid, clock_command, response=False)

    def parse_notification(self, data: bytes) -> ScaleReading | None:
        if len(data) < 5 or data[0] != 0xCF:
            return None

        raw_weight = uint16_le(data, 3)
        impedance = 0.0
        if len(data) >= 10:
            raw_impedance = ((data[2] << 8) + data[1]) * 0.1
            if data[9] != 1 and raw_impedance != 0:
                impedance = raw_impedance

        self._weight_stable = self._previous_raw_weight == raw_weight
        self._previous_raw_weight = raw_weight
        return ScaleReading(raw_weight / 100, impedance)

    def is_final(self, reading: ScaleReading) -> bool:
        return self._weight_stable


class OneByoneNewAdapter(ScaleAdapter):
    """Newer 1byone Scale protocol."""

    key = "one_byone_new"
    name = "1byone Scale (new)"
    priority = 60
    exact_names = ("1byone scale",)
    char_notify_uuid = uuid16(0xFFB2)
    char_write_uuid = uuid16(0xFFB1)
    unlock_command = bytes(
        [
            0xAB,
            0x2A,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0xD7,
        ]
    )

    def __init__(self) -> None:
        self._weight = 0.0
        self._impedance = 0.0

    async def on_connected(self, context: ConnectionContext) -> None:
        self._weight = 0.0
        self._impedance = 0.0

    def parse_notification(self, data: bytes) -> ScaleReading | None:
        if len(data) < 3 or data[0:2] != b"\xab\x2a":
            return None

        frame_type = data[2]
        if frame_type == 0x80 and len(data) >= 6:
            raw = int.from_bytes(data[3:6], "big")
            self._weight = (raw & 0x03FFFF) / 1000
        elif frame_type == 0x01 and len(data) >= 6:
            self._impedance = int.from_bytes(data[4:6], "big")
        elif frame_type == 0x00 and len(data) >= 8 and data[7] == 0x80:
            return None

        if self._weight <= 0:
            return None
        return ScaleReading(self._weight, self._impedance)

    def is_complete(self, reading: ScaleReading) -> bool:
        return reading.weight > 0 and reading.impedance > 0
