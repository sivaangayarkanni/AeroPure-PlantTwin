"""Command line: run a week of plant time and emit CPCB + economics artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .physics import GENSET_LIBRARY
from .plant import PlantTwin, iter_quarter_hours, textile_cluster_week


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="AeroPure plant digital twin")
    p.add_argument("--genset", default="250kVA", choices=sorted(GENSET_LIBRARY))
    p.add_argument("--hours", type=int, default=168, help="simulated operating hours")
    p.add_argument("--out", default="data/run", help="output directory")
    args = p.parse_args(argv)

    plant = PlantTwin(genset_key=args.genset)
    hourly = textile_cluster_week(args.hours)
    plant.run_profile(list(iter_quarter_hours(hourly)), dt_h=0.25)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    plant.write_telemetry(out / "cpcb_telemetry.jsonl")
    summary = plant.summary()
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
