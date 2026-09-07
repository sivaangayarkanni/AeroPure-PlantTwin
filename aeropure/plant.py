"""Discrete-time plant digital twin with CPCB telemetry and cash flows."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterator

from .economics import Tariff, carbon_to_inr, diesel_to_inr, heat_to_inr
from .physics import (
    CPCB_STACK_PM_G_PER_KWH,
    GENSET_LIBRARY,
    GensetSpec,
    ModuleState,
    bypass_controller,
    bsfc_l_per_kwh,
    capture_efficiency,
    delta_p_mbar,
    fuel_penalty_frac,
    heat_recovery_kw,
    load_to_thermal,
)


@dataclass
class StepResult:
    t_h: float
    load_frac: float
    kw: float
    t_exh_in_c: float
    t_exh_out_c: float
    q_whr_kw: float
    kwh_elec: float
    litres_base: float
    litres_actual: float
    litres_saved_vs_blind: float
    pm_in_g: float
    pm_out_g: float
    carbon_harvest_kg: float
    cake_kg: float
    cake_frac: float
    eta_capture: float
    dp_mbar: float
    bypass: float
    fuel_penalty: float
    cpcb_ok: bool
    heat_inr: float
    carbon_inr: float
    diesel_inr: float
    diesel_avoided_inr: float


@dataclass
class PlantTwin:
    genset_key: str = "250kVA"
    water_in_c: float = 32.0
    hx_effectiveness: float = 0.62
    tariff: Tariff = field(default_factory=Tariff)
    state: ModuleState = field(default_factory=ModuleState)
    log: list = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.genset_key not in GENSET_LIBRARY:
            raise KeyError(f"Unknown genset {self.genset_key}")
        self.spec: GensetSpec = GENSET_LIBRARY[self.genset_key]

    def step(self, load_frac: float, dt_h: float) -> StepResult:
        spec = self.spec
        st = self.state
        kw, t_in, m_dot = load_to_thermal(load_frac, spec)
        q_kw, t_out = heat_recovery_kw(t_in, m_dot, self.water_in_c, self.hx_effectiveness)
        cake_frac = st.cake_kg / max(st.cartridge_capacity_kg, 1e-6)
        bypass = 0.0
        dp = delta_p_mbar(cake_frac, load_frac, bypass)
        bypass = bypass_controller(dp, cake_frac, load_frac)
        dp = delta_p_mbar(cake_frac, load_frac, bypass)
        eta = capture_efficiency(cake_frac, bypass)
        pen = fuel_penalty_frac(dp)
        kwh = kw * dt_h
        litres_base = bsfc_l_per_kwh(load_frac, spec) * kwh
        litres_actual = litres_base * (1.0 + pen)
        dp_blind = delta_p_mbar(min(1.0, cake_frac + 0.35), load_frac, 0.0)
        litres_blind = litres_base * (1.0 + fuel_penalty_frac(dp_blind))
        litres_saved = max(0.0, litres_blind - litres_actual)
        pm_in = spec.raw_pm_g_per_kwh * kwh
        pm_out = pm_in * (1.0 - eta)
        carbon_kg = (pm_in - pm_out) * spec.raw_carbon_fraction / 1000.0
        st.cake_kg += carbon_kg
        st.harvested_kg += carbon_kg
        st.hours += dt_h
        if st.cake_kg >= st.cartridge_capacity_kg * 0.96:
            st.cake_kg = 0.05
            st.service_events += 1
        stack_g_per_kwh = (pm_out / kwh) if kwh > 0 else 0.0
        cpcb_ok = stack_g_per_kwh <= CPCB_STACK_PM_G_PER_KWH and not (bypass > 0.4 and load_frac > 0.6)
        rec = StepResult(
            t_h=st.hours, load_frac=load_frac, kw=kw, t_exh_in_c=t_in, t_exh_out_c=t_out,
            q_whr_kw=q_kw, kwh_elec=kwh, litres_base=litres_base, litres_actual=litres_actual,
            litres_saved_vs_blind=litres_saved, pm_in_g=pm_in, pm_out_g=pm_out,
            carbon_harvest_kg=carbon_kg, cake_kg=st.cake_kg,
            cake_frac=st.cake_kg / st.cartridge_capacity_kg, eta_capture=eta, dp_mbar=dp,
            bypass=bypass, fuel_penalty=pen, cpcb_ok=cpcb_ok,
            heat_inr=heat_to_inr(q_kw * dt_h, self.tariff),
            carbon_inr=carbon_to_inr(carbon_kg, self.tariff),
            diesel_inr=diesel_to_inr(litres_actual, self.tariff),
            diesel_avoided_inr=diesel_to_inr(litres_saved, self.tariff),
        )
        self.log.append(rec)
        return rec

    def run_profile(self, loads, dt_h: float = 0.25):
        return [self.step(lf, dt_h) for lf in loads]

    def summary(self) -> dict:
        if not self.log:
            return {}
        kwh = sum(r.kwh_elec for r in self.log)
        heat_kwh = 0.0
        prev = 0.0
        for r in self.log:
            dt = r.t_h - prev
            prev = r.t_h
            heat_kwh += r.q_whr_kw * dt
        pm_in = sum(r.pm_in_g for r in self.log)
        pm_out = sum(r.pm_out_g for r in self.log)
        carbon = sum(r.carbon_harvest_kg for r in self.log)
        heat_inr = sum(r.heat_inr for r in self.log)
        carbon_inr = sum(r.carbon_inr for r in self.log)
        diesel_avoid = sum(r.diesel_avoided_inr for r in self.log)
        hours = self.state.hours
        compliant = sum(1 for r in self.log if r.cpcb_ok) / len(self.log)
        days = max(hours / 24.0, 1e-6)
        fine_risk_without = self.tariff.daily_shutdown_fine_inr * days * 0.12
        fine_risk_with = fine_risk_without * (1.0 - compliant) * 0.15
        opex_cartridges = self.state.service_events * self.tariff.cartridge_inr
        net = heat_inr + carbon_inr + diesel_avoid + (fine_risk_without - fine_risk_with) - opex_cartridges
        payback_days = self.tariff.module_capex_inr / (net / days) if net > 0 else float("inf")
        return {
            "genset": self.spec.name,
            "rated_kw": self.spec.rated_kw,
            "hours": round(hours, 2),
            "kwh_elec": round(kwh, 1),
            "kwh_th_recovered": round(heat_kwh, 1),
            "diesel_litres": round(sum(r.litres_actual for r in self.log), 1),
            "pm_in_g": round(pm_in, 1),
            "pm_out_g": round(pm_out, 1),
            "capture_pct": round(100.0 * (1.0 - pm_out / pm_in), 2) if pm_in else 0.0,
            "carbon_black_kg": round(carbon, 3),
            "service_swaps": self.state.service_events,
            "cpcb_compliance_frac": round(compliant, 4),
            "inr_heat": round(heat_inr, 0),
            "inr_carbon": round(carbon_inr, 0),
            "inr_fuel_saved": round(diesel_avoid, 0),
            "inr_fine_shield": round(fine_risk_without - fine_risk_with, 0),
            "inr_cartridge_opex": opex_cartridges,
            "inr_net": round(net, 0),
            "payback_days_at_this_duty": None if payback_days == float("inf") else round(payback_days, 1),
            "three_mechanisms": {
                "material_sales": round(carbon_inr, 0),
                "fuel_and_thermal_savings": round(heat_inr + diesel_avoid, 0),
                "revenue_protection": round(fine_risk_without - fine_risk_with, 0),
            },
        }

    def write_telemetry(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for r in self.log:
                f.write(json.dumps(asdict(r), ensure_ascii=False) + "\n")


def textile_cluster_week(hours: int = 168, seed: int = 7) -> list:
    loads = []
    x = seed
    for h in range(hours):
        x = (1103515245 * x + 12345) & 0x7FFFFFFF
        noise = ((x % 1000) / 1000.0 - 0.5) * 0.08
        dow = (h // 24) % 7
        hod = h % 24
        if dow == 6:
            base = 0.28 if 8 <= hod <= 16 else 0.12
        elif 8 <= hod < 13 or 14 <= hod < 22:
            base = 0.78
        elif hod >= 22 or hod < 6:
            base = 0.92 if hod >= 22 or hod < 2 else 0.45
        else:
            base = 0.55
        loads.append(max(0.08, min(1.02, base + noise)))
    return loads


def iter_quarter_hours(loads_hourly):
    for lf in loads_hourly:
        yield lf
        yield min(1.02, lf * 1.02)
        yield lf
        yield max(0.08, lf * 0.96)
