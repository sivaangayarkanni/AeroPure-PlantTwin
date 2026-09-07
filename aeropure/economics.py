"""Unit economics for an Indian industrial site (INR, 2026 planning rates)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Tariff:
    diesel_inr_per_l: float = 94.0
    boiler_fuel_inr_per_kwh_th: float = 7.8
    carbon_black_inr_per_kg: float = 85.0
    daily_shutdown_fine_inr: float = 50_000.0
    cartridge_inr: float = 6_800.0
    module_capex_inr: float = 3_40_000.0


DEFAULT_TARIFF = Tariff()


def heat_to_inr(kwh_th: float, t: Tariff = DEFAULT_TARIFF) -> float:
    return kwh_th * t.boiler_fuel_inr_per_kwh_th


def diesel_to_inr(litres: float, t: Tariff = DEFAULT_TARIFF) -> float:
    return litres * t.diesel_inr_per_l


def carbon_to_inr(kg: float, t: Tariff = DEFAULT_TARIFF) -> float:
    return kg * t.carbon_black_inr_per_kg
