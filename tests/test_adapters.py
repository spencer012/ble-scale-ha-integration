"""Tests for scale protocol selection."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
import sys
from types import ModuleType
import unittest

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


if __name__ == "__main__":
    unittest.main()
