"""Body-composition calculations ported from ble-scale-sync.

This file is a modified Python port of GPL-3.0-licensed ble-scale-sync,
copyright (C) 2026 Kristián Partl.
"""

from __future__ import annotations

from math import floor

from .models import BodyComposition, ScaleBodyComp, UserProfile


def compute_bia_fat(
    weight: float, impedance: float, profile: UserProfile
) -> float:
    """Estimate body-fat percentage from bioelectrical impedance."""
    if weight <= 0 or impedance <= 0:
        return 0.0

    if profile.gender == "male":
        coefficients = (
            (0.637, 0.205, -0.18, 12.5)
            if profile.is_athlete
            else (0.503, 0.165, -0.158, 17.8)
        )
    else:
        coefficients = (
            (0.55, 0.18, -0.15, 8.5)
            if profile.is_athlete
            else (0.49, 0.15, -0.13, 11.5)
        )

    c1, c2, c3, c4 = coefficients
    lean_mass = (
        c1 * profile.height**2 / impedance
        + c2 * weight
        + c3 * profile.age
        + c4
    )
    if lean_mass > weight:
        lean_mass = weight * 0.96

    return max(3.0, min(((weight - lean_mass) / weight) * 100, 60.0))


def build_payload(
    weight: float,
    impedance: float,
    comp: ScaleBodyComp,
    profile: UserProfile,
) -> BodyComposition:
    """Combine scale-provided values with profile-derived metrics."""
    if weight <= 0:
        return BodyComposition(
            weight=_round2(weight),
            impedance=_round2(impedance),
            bmi=0.0,
            body_fat_percent=0.0,
            water_percent=0.0,
            bone_mass=0.0,
            muscle_mass=0.0,
            visceral_fat=1,
            physique_rating=1,
            bmr=0,
            metabolic_age=profile.age,
        )

    height_m = profile.height / 100
    bmi = weight / (height_m * height_m)
    body_fat = (
        comp.fat if comp.fat is not None else estimate_body_fat(bmi, profile)
    )
    lean_mass = weight * (1 - body_fat / 100)
    water = (
        comp.water
        if comp.water is not None
        else (lean_mass * (0.74 if profile.is_athlete else 0.73) / weight) * 100
    )
    bone = comp.bone if comp.bone is not None else lean_mass * 0.042
    skeletal_muscle = lean_mass * (0.6 if profile.is_athlete else 0.54)
    muscle = (
        (comp.muscle / 100) * weight
        if comp.muscle is not None
        else lean_mass - bone
    )

    if comp.visceral_fat is not None:
        visceral = max(1, min(int(comp.visceral_fat), 59))
    elif body_fat > 10:
        visceral = max(
            1, min(int(body_fat * 0.55 - 4 + profile.age * 0.08), 59)
        )
    else:
        visceral = 1

    physique = compute_physique_rating(
        body_fat,
        (comp.muscle / 100) * weight
        if comp.muscle is not None
        else skeletal_muscle,
        weight,
    )

    bmr_value = (
        10 * weight
        + 6.25 * profile.height
        - 5 * profile.age
        + (5 if profile.gender == "male" else -161)
    )
    if profile.is_athlete:
        bmr_value *= 1.05

    ideal_bmr = 10 * weight + 6.25 * profile.height - 5 * 25 + 5
    metabolic_age = profile.age + int((ideal_bmr - bmr_value) / 15)
    metabolic_age = max(12, metabolic_age)
    if profile.is_athlete and metabolic_age > profile.age:
        metabolic_age = profile.age - 5

    return BodyComposition(
        weight=_round2(weight),
        impedance=_round2(impedance),
        bmi=_round2(bmi),
        body_fat_percent=_round2(body_fat),
        water_percent=_round2(water),
        bone_mass=_round2(bone),
        muscle_mass=_round2(muscle),
        visceral_fat=visceral,
        physique_rating=physique,
        bmr=int(bmr_value),
        metabolic_age=metabolic_age,
    )


def estimate_body_fat(bmi: float, profile: UserProfile) -> float:
    """Estimate body fat using the Deurenberg formula."""
    sex_factor = 1 if profile.gender == "male" else 0
    body_fat = (
        1.2 * bmi + 0.23 * profile.age - 10.8 * sex_factor - 5.4
    )
    if profile.is_athlete:
        body_fat *= 0.85
    return max(3.0, min(body_fat, 60.0))


def compute_physique_rating(
    body_fat_percent: float, skeletal_muscle_mass: float, weight: float
) -> int:
    """Return the 1-to-9 physique rating used by ble-scale-sync."""
    if body_fat_percent > 25:
        return 2 if skeletal_muscle_mass > weight * 0.4 else 1
    if body_fat_percent < 18:
        if skeletal_muscle_mass > weight * 0.45:
            return 9
        if skeletal_muscle_mass > weight * 0.4:
            return 8
        return 7
    if skeletal_muscle_mass > weight * 0.45:
        return 6
    if skeletal_muscle_mass < weight * 0.38:
        return 4
    return 5


def uuid16(code: int) -> str:
    """Expand a 16-bit Bluetooth UUID."""
    return f"0000{code:04x}-0000-1000-8000-00805f9b34fb"


def xor_checksum(data: bytes | bytearray | list[int]) -> int:
    """Return the XOR of all bytes."""
    result = 0
    for value in data:
        result ^= value & 0xFF
    return result & 0xFF


def _round2(value: float) -> float:
    return floor(value * 100 + 0.5) / 100
