"""Excelvan CF369 scale protocol."""

from __future__ import annotations

from ..body_comp import build_payload, uuid16, xor_checksum
from ..models import BodyComposition, ScaleBodyComp, ScaleReading, UserProfile
from .base import ConnectionContext, ScaleAdapter, profile_byte, uint16_be


class ExcelvanCF369Adapter(ScaleAdapter):
    """Excelvan CF369 / Electronic Scale devices."""

    key = "excelvan_cf369"
    name = "Excelvan CF369"
    priority = 110
    exact_names = ("electronic scale",)
    char_notify_uuid = uuid16(0xFFF4)
    char_write_uuid = uuid16(0xFFF1)

    def __init__(self) -> None:
        self._comp = ScaleBodyComp()

    async def on_connected(self, context: ConnectionContext) -> None:
        self._comp = ScaleBodyComp()
        profile = context.profile
        command = bytearray(
            [
                0xFE,
                0x01,
                0x01 if profile.gender == "male" else 0x00,
                0x01,
                profile_byte(profile.height),
                profile_byte(profile.age),
                0x01,
            ]
        )
        command.append(xor_checksum(command[1:7]))
        await context.write(self.char_write_uuid, bytes(command), response=False)

    def parse_notification(self, data: bytes) -> ScaleReading | None:
        if len(data) < 14 or data[0] != 0xCF:
            return None
        weight = uint16_be(data, 4) / 10
        if weight <= 0:
            return None

        complete = data[6] != 0xFF
        self._comp = ScaleBodyComp(
            fat=uint16_be(data, 6) / 10 if complete else None,
            bone=data[8] / 10 if complete else None,
            muscle=uint16_be(data, 9) / 10 if complete else None,
            visceral_fat=float(data[11]) if complete else None,
            water=uint16_be(data, 12) / 10 if complete else None,
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
