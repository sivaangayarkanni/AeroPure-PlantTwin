from aeropure.physics import (
    GENSET_LIBRARY,
    delta_p_mbar,
    heat_recovery_kw,
    load_to_thermal,
)
from aeropure.plant import PlantTwin, textile_cluster_week, iter_quarter_hours


def test_heat_recovery_positive():
    spec = GENSET_LIBRARY["250kVA"]
    kw, t, m = load_to_thermal(0.75, spec)
    q, tout = heat_recovery_kw(t, m, 32.0)
    assert q > 20
    assert tout < t


def test_cake_raises_dp():
    assert delta_p_mbar(0.9, 0.8, 0.0) > delta_p_mbar(0.1, 0.8, 0.0)


def test_bypass_cuts_dp():
    assert delta_p_mbar(0.7, 0.9, 0.3) < delta_p_mbar(0.7, 0.9, 0.0)


def test_week_runs_and_complies():
    plant = PlantTwin("125kVA")
    plant.run_profile(list(iter_quarter_hours(textile_cluster_week(24))), dt_h=0.25)
    s = plant.summary()
    assert s["hours"] == 24
    assert s["capture_pct"] > 80
    assert s["cpcb_compliance_frac"] > 0.9
    assert s["carbon_black_kg"] > 0
