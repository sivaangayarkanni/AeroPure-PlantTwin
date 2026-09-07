"""Industry control-room API (FastAPI)."""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel, Field

from .physics import GENSET_LIBRARY
from .plant import PlantTwin, textile_cluster_week, iter_quarter_hours

app = FastAPI(
    title="AeroPure Plant Twin",
    version="1.0.0",
    description="Digital twin for modular resource-recovery exhaust purifier.",
)

_plants: dict[str, PlantTwin] = {}


class SimRequest(BaseModel):
    plant_id: str = "TN-KARUR-WEAVE-01"
    genset: str = "250kVA"
    hours: int = Field(48, ge=1, le=24 * 30)


@app.get("/health")
def health() -> dict:
    return {"ok": True, "gensets": list(GENSET_LIBRARY)}


@app.post("/simulate")
def simulate(req: SimRequest) -> dict:
    plant = PlantTwin(genset_key=req.genset)
    hourly = textile_cluster_week(req.hours)
    plant.run_profile(list(iter_quarter_hours(hourly)), dt_h=0.25)
    _plants[req.plant_id] = plant
    return {"plant_id": req.plant_id, "summary": plant.summary(), "points": len(plant.log)}


@app.get("/plants/{plant_id}/telemetry")
def telemetry(plant_id: str, tail: int = 40) -> dict:
    plant = _plants.get(plant_id)
    if plant is None:
        return {"error": "unknown plant_id — POST /simulate first"}
    sl = plant.log[-tail:]
    return {
        "plant_id": plant_id,
        "n": len(plant.log),
        "tail": [
            {
                "t_h": r.t_h,
                "kw": round(r.kw, 1),
                "pm_out_g": round(r.pm_out_g, 3),
                "dp_mbar": round(r.dp_mbar, 1),
                "bypass": round(r.bypass, 2),
                "cpcb_ok": r.cpcb_ok,
                "cake_frac": round(r.cake_frac, 3),
            }
            for r in sl
        ],
    }
