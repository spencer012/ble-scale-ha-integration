"""Tests for scale protocol selection."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
import sys
from types import ModuleType
import unittest
from unittest.mock import patch

PACKAGE_PATH = (
    Path(__file__).parents[1] / "custom_components" / "ble_scale"
)
package = ModuleType("custom_components.ble_scale")
package.__path__ = [str(PACKAGE_PATH)]
sys.modules["custom_components.ble_scale"] = package

uuid16 = import_module("custom_components.ble_scale.body_comp").uuid16
scales = import_module("custom_components.ble_scale.scales")
DeviceInfo = scales.DeviceInfo
resolve_adapter = scales.resolve_adapter
one_byone = import_module("custom_components.ble_scale.scales.one_byone")


class AdapterResolutionTest(unittest.TestCase):
    """Ensure generic services do not override explicit device names."""

    def test_health_scale_uses_one_byone_protocol(self) -> None:
        adapter = resolve_adapter(
            DeviceInfo(
                local_name="Health Scale",
                service_uuids=(uuid16(0xFFF0),),
            )
        )

        self.assertIsNotNone(adapter)
        self.assertEqual(adapter.key, "one_byone")

    def test_named_inlife_scale_uses_inlife_protocol(self) -> None:
        adapter = resolve_adapter(
            DeviceInfo(
                local_name="000FatScale01",
                service_uuids=(uuid16(0xFFF0),),
            )
        )

        self.assertIsNotNone(adapter)
        self.assertEqual(adapter.key, "inlife")

    def test_nameless_fff0_device_keeps_inlife_fallback(self) -> None:
        adapter = resolve_adapter(
            DeviceInfo(local_name="", service_uuids=(uuid16(0xFFF0),))
        )

        self.assertIsNotNone(adapter)
        self.assertEqual(adapter.key, "inlife")


class OneByoneStabilityTest(unittest.TestCase):
    """Ensure transient plateaus are not published as final weight."""

    @staticmethod
    def _frame(weight_kg: float) -> bytes:
        frame = bytearray(10)
        frame[0] = 0xCF
        frame[3:5] = round(weight_kg * 100).to_bytes(2, "little")
        frame[9] = 1
        return bytes(frame)

    def test_requires_settling_time_and_stable_window(self) -> None:
        adapter = one_byone.OneByoneAdapter()

        with patch.object(
            one_byone,
            "monotonic",
            side_effect=[0.0, 1.0, 2.0, 3.0, 4.0, 5.0],
        ):
            for _ in range(3):
                reading = adapter.parse_notification(self._frame(20.0))
                self.assertFalse(adapter.is_final(reading))

            reading = adapter.parse_notification(self._frame(80.0))
            self.assertFalse(adapter.is_final(reading))
            reading = adapter.parse_notification(self._frame(80.05))
            self.assertFalse(adapter.is_final(reading))
            reading = adapter.parse_notification(self._frame(80.02))
            self.assertTrue(adapter.is_final(reading))

    def test_uses_longer_fallback_hold(self) -> None:
        adapter = one_byone.OneByoneAdapter()

        self.assertEqual(adapter.completion_hold, 12.0)


if __name__ == "__main__":
    unittest.main()
