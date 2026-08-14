"""Sensor entities for BLE Scale."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfMass,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import BleScaleConfigEntry
from .const import DOMAIN
from .models import ScaleMeasurement

SensorValue = StateType | datetime | Decimal


@dataclass(frozen=True, kw_only=True)
class BleScaleSensorDescription(SensorEntityDescription):
    """Describe one value in a completed scale measurement."""

    value_fn: Callable[[ScaleMeasurement], SensorValue]


SENSORS: tuple[BleScaleSensorDescription, ...] = (
    BleScaleSensorDescription(
        key="weight",
        translation_key="weight",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda reading: reading.body.weight,
    ),
    BleScaleSensorDescription(
        key="bmi",
        translation_key="bmi",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        icon="mdi:human-male-height-variant",
        value_fn=lambda reading: reading.body.bmi,
    ),
    BleScaleSensorDescription(
        key="body_fat_percent",
        translation_key="body_fat_percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        icon="mdi:percent",
        value_fn=lambda reading: reading.body.body_fat_percent,
    ),
    BleScaleSensorDescription(
        key="water_percent",
        translation_key="water_percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        icon="mdi:water-percent",
        value_fn=lambda reading: reading.body.water_percent,
    ),
    BleScaleSensorDescription(
        key="muscle_mass",
        translation_key="muscle_mass",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        icon="mdi:arm-flex",
        value_fn=lambda reading: reading.body.muscle_mass,
    ),
    BleScaleSensorDescription(
        key="bone_mass",
        translation_key="bone_mass",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        icon="mdi:bone",
        value_fn=lambda reading: reading.body.bone_mass,
    ),
    BleScaleSensorDescription(
        key="visceral_fat",
        translation_key="visceral_fat",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:human",
        value_fn=lambda reading: reading.body.visceral_fat,
    ),
    BleScaleSensorDescription(
        key="physique_rating",
        translation_key="physique_rating",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:human-handsup",
        value_fn=lambda reading: reading.body.physique_rating,
    ),
    BleScaleSensorDescription(
        key="bmr",
        translation_key="bmr",
        native_unit_of_measurement="kcal/day",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:fire",
        value_fn=lambda reading: reading.body.bmr,
    ),
    BleScaleSensorDescription(
        key="metabolic_age",
        translation_key="metabolic_age",
        native_unit_of_measurement=UnitOfTime.YEARS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:calendar-account",
        value_fn=lambda reading: reading.body.metabolic_age,
    ),
    BleScaleSensorDescription(
        key="impedance",
        translation_key="impedance",
        native_unit_of_measurement="Ω",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        icon="mdi:omega",
        value_fn=lambda reading: reading.body.impedance,
    ),
    BleScaleSensorDescription(
        key="last_measurement",
        translation_key="last_measurement",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda reading: reading.measured_at,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BleScaleConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the scale's sensor entities."""
    async_add_entities(
        BleScaleSensor(entry, description) for description in SENSORS
    )


class BleScaleSensor(RestoreSensor):
    """A restored sensor updated when a complete scale reading arrives."""

    entity_description: BleScaleSensorDescription
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        entry: BleScaleConfigEntry,
        description: BleScaleSensorDescription,
    ) -> None:
        self.entity_description = description
        self._coordinator = entry.runtime_data
        self._attr_unique_id = f"{entry.unique_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
            connections={
                (dr.CONNECTION_BLUETOOTH, self._coordinator.address)
            },
            name=entry.title,
            manufacturer="BLE Scale",
            model=self._coordinator.adapter.name,
        )

    async def async_added_to_hass(self) -> None:
        """Restore a prior value and subscribe to completed readings."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._coordinator.async_add_listener(
                self._handle_coordinator_update
            )
        )
        if self._coordinator.data is not None:
            self._set_value(self._coordinator.data)
            return
        restored = await self.async_get_last_sensor_data()
        if self._coordinator.data is not None:
            self._set_value(self._coordinator.data)
        elif restored is not None:
            self._attr_native_value = restored.native_value

    @callback
    def _handle_coordinator_update(self) -> None:
        if self._coordinator.data is None:
            return
        self._set_value(self._coordinator.data)
        self.async_write_ha_state()

    @callback
    def _set_value(self, measurement: ScaleMeasurement) -> None:
        self._attr_native_value = self.entity_description.value_fn(measurement)
