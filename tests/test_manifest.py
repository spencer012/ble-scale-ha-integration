"""Regression tests for Bluetooth manifest matchers."""

from __future__ import annotations

import json
from pathlib import Path
import unittest

MANIFEST_PATH = (
    Path(__file__).parents[1]
    / "custom_components"
    / "ble_scale"
    / "manifest.json"
)


class BluetoothManifestTest(unittest.TestCase):
    """Validate constraints enforced while HA builds its global matcher index."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    def test_local_name_matchers_have_literal_prefix(self) -> None:
        """Wildcards in the first three characters break all HA Bluetooth."""
        for matcher in self.manifest["bluetooth"]:
            if local_name := matcher.get("local_name"):
                with self.subTest(local_name=local_name):
                    self.assertFalse(
                        {"*", "?"} & set(local_name[:3]),
                        "HA requires the first three characters to be literal",
                    )

    def test_all_scale_matchers_require_connectable_route(self) -> None:
        """These GATT scales must only be discovered through connectable paths."""
        for matcher in self.manifest["bluetooth"]:
            with self.subTest(matcher=matcher):
                self.assertIs(matcher.get("connectable"), True)


if __name__ == "__main__":
    unittest.main()
