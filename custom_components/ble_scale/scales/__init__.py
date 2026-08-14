"""Supported BLE scale protocol registry."""

from __future__ import annotations

from collections.abc import Iterable

from .base import DeviceInfo, ScaleAdapter
from .digoo import DigooScaleAdapter
from .excelvan import ExcelvanCF369Adapter
from .exingtech import ExingtechY1Adapter
from .hesley import HesleyScaleAdapter
from .hoffen import HoffenAdapter
from .inlife import InlifeScaleAdapter
from .one_byone import OneByoneAdapter, OneByoneNewAdapter
from .senssun import SenssunAdapter

ADAPTER_TYPES: tuple[type[ScaleAdapter], ...] = tuple(
    sorted(
        (
            OneByoneAdapter,
            OneByoneNewAdapter,
            InlifeScaleAdapter,
            HesleyScaleAdapter,
            HoffenAdapter,
            DigooScaleAdapter,
            ExcelvanCF369Adapter,
            ExingtechY1Adapter,
            SenssunAdapter,
        ),
        key=lambda adapter_type: adapter_type.priority,
        reverse=True,
    )
)

ADAPTER_NAMES = {
    adapter_type.key: adapter_type.name for adapter_type in ADAPTER_TYPES
}


def resolve_adapter(device: DeviceInfo) -> ScaleAdapter | None:
    """Create the highest-priority adapter matching a Bluetooth device."""
    for adapter_type in ADAPTER_TYPES:
        adapter = adapter_type()
        if adapter.matches(device):
            return adapter
    return None


def adapter_for_key(key: str) -> ScaleAdapter:
    """Create an adapter by its stable config key."""
    for adapter_type in ADAPTER_TYPES:
        if adapter_type.key == key:
            return adapter_type()
    raise ValueError(f"Unsupported scale adapter: {key}")


def names_for_discovery() -> Iterable[str]:
    """Yield all exact and substring discovery name tokens."""
    for adapter_type in ADAPTER_TYPES:
        yield from adapter_type.exact_names
        yield from adapter_type.included_names


__all__ = [
    "ADAPTER_NAMES",
    "ADAPTER_TYPES",
    "DeviceInfo",
    "ScaleAdapter",
    "adapter_for_key",
    "resolve_adapter",
]
