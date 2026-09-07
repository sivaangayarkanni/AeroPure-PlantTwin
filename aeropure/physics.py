"""0-D / 1-D plant physics for an Indian diesel genset + AeroPure module."""

from __future__ import annotations

import math
from dataclasses import dataclass

CPCB_STACK_PM_G_PER_KWH = 0.03
CPCB_STACK_PM_MG_NM3_DISPLAY = 50.0


@dataclass(frozen=True)
class GensetSpec:
    name: str
    rated_kw: float
    displacement_hint: str
    exhaust_kg_per_kwh: float = 8.2
    bsfc_l_per_kwh_full: float = 0.265
    t_exh_idle_c: float = 220.0
    t_exh_full_c: float = 490.0
    raw_pm_g_per_kwh: float = 0.28
    raw_carbon_fraction: float = 0.72


GENSET_LIBRARY = {
    "62.5kVA": GensetSpec("Kirloskar-class 62.5 kVA", 50.0, "3.3 L"),
    "125kVA": GensetSpec("Cummins-class 125 kVA", 100.0, "5.9 L"),
    "250kVA": GensetSpec("Ashok Leyland-class 250 kVA", 200.0, "8.9 L", raw_pm_g_per_kwh=0.26),
    "500kVA": GensetSpec("Caterpillar-class 500 kVA", 400.0, "15 L", raw_pm_g_per_kwh=0.24),
}


@dataclass
class ModuleState:
    cake_kg: float = 0.0
    cartridge_capacity_kg: float = 4.8
    bypass_open: float = 0.0
    hours: float = 0.0
    harvested_kg: float = 0.0
    service_events: int = 0


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def load_to_thermal(load_frac: float, spec: GensetSpec) -> tuple[float, float, float]:
    lf = clamp(load_frac, 0.05, 1.05)
    kw = spec.rated_kw * lf
    t = spec.t_exh_idle_c + (spec.t_exh_full_c - spec.t_exh_idle_c) * (lf**0.85)
    m_dot = (spec.exhaust_kg_per_kwh * kw) / 3600.0
    return kw, t, m_dot


def bsfc_l_per_kwh(load_frac: float, spec: GensetSpec) -> float:
    lf = clamp(load_frac, 0.08, 1.05)
    return spec.bsfc_l_per_kwh_full * (1.18 - 0.28 * lf + 0.22 * (lf - 0.75) ** 2)


def heat_recovery_kw(t_exh_c: float, m_dot_kg_s: float, t_water_in_c: float, effectiveness: float = 0.62, cp_exh: float = 1.10) -> tuple[float, float]:
    if m_dot_kg_s <= 0:
        return 0.0, t_exh_c
    q_max = m_dot_kg_s * cp_exh * max(0.0, t_exh_c - t_water_in_c)
    q = effectiveness * q_max
    dt = q / (m_dot_kg_s * cp_exh) if m_dot_kg_s > 0 else 0.0
    return q, t_exh_c - dt


def capture_efficiency(cake_frac: float, bypass: float) -> float:
    base = 0.965
    assist = 0.018 * math.exp(-((cake_frac - 0.25) ** 2) / 0.08)
    blind = 0.22 * max(0.0, cake_frac - 0.55) ** 1.4
    eta = clamp(base + assist - blind, 0.55, 0.985)
    return eta * (1.0 - 0.92 * bypass)


def delta_p_mbar(cake_frac: float, load_frac: float, bypass: float) -> float:
    dp0 = 18.0 + 22.0 * load_frac**1.4
    dp_cake = 95.0 * (cake_frac**2)
    return (dp0 + dp_cake) * (1.0 - 0.75 * bypass)


def fuel_penalty_frac(dp_mbar: float) -> float:
    extra = max(0.0, dp_mbar - 28.0)
    return clamp(0.0105 * (extra / 40.0), 0.0, 0.07)


def bypass_controller(dp_mbar: float, cake_frac: float, load_frac: float) -> float:
    if cake_frac > 0.92:
        return 0.55
    if dp_mbar > 85 and load_frac > 0.7:
        return clamp((dp_mbar - 85) / 80.0, 0.0, 0.35)
    return 0.0
