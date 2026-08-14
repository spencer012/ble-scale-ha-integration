"""Data models for BLE scales."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

Gender = Literal["male", "female"]


@dataclass(frozen=True, slots=True)
class UserProfile:
    """Personal data used by scale protocols and derived metrics."""

    height: float
    age: int
    gender: Gender
    is_athlete: bool


@dataclass(frozen=True, slots=True)
class ScaleReading:
    """Raw measurement decoded from a scale."""

    weight: float
    impedance: float = 0.0


@dataclass(frozen=True, slots=True)
class ScaleBodyComp:
    """Body-composition values provided by a scale."""

    fat: float | None = None
    water: float | None = None
    muscle: float | None = None
    bone: float | None = None
    visceral_fat: float | None = None


@dataclass(frozen=True, slots=True)
class BodyComposition:
    """Complete measured and derived body-composition payload."""

    weight: float
    impedance: float
    bmi: float
    body_fat_percent: float
    water_percent: float
    bone_mass: float
    muscle_mass: float
    visceral_fat: int
    physique_rating: int
    bmr: int
    metabolic_age: int


@dataclass(frozen=True, slots=True)
class ScaleMeasurement:
    """A completed body-composition measurement."""

    body: BodyComposition
    measured_at: datetime
