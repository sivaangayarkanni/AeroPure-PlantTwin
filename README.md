# AeroPure Plant Twin

Industry-grade **digital twin** of the AeroPure modular resource-recovery exhaust purifier.

GitHub: https://github.com/sivaangayarkanni/AeroPure-PlantTwin

This is **not** a pretty animation pretending to be CFD. It is a 0-D / 1-D plant model a commissioning engineer would actually sign: heat-exchanger effectiveness, filter-cake dP, fuel penalty from backpressure, cartridge swap opex, and CPCB-style 15-minute telemetry.

## What it models (production stack)

| Stage | Plant function | Cash mechanism |
|---|---|---|
| 1 Waste-heat recovery exchanger | Effectiveness-NTU gas-to-water, preheats 32 C utility header | Displaces boiler / FO heat |
| 2 Carbon-black nano-matrix | Capture eta vs cake fraction; dry kg logged | Pigment / ink sale |
| 3 Dynamic backpressure bypass | Opens only on dP spike or blind cartridge | Stops 3-5% extra HSD burn |
| 4 6-layer array + IoT node | Stack PM vs 0.03 g/kWh plant cap, JSONL log | Fine shield (CPCB / SPCB) |

## Indian duty cycle

Default profile is a **Karur / Tiruppur weave cluster week**: two-shift load, Sunday half-day, late-night grid-dip when every DG on the feeder starts.

Genset library: `62.5kVA` · `125kVA` · `250kVA` · `500kVA`.

## Run locally

```bash
python -m pip install -r requirements.txt
python -m aeropure.cli --genset 250kVA --hours 168 --out data/run
pytest -q
uvicorn aeropure.api:app --port 8080
```

API:

- `GET /health`
- `POST /simulate` `{"plant_id":"TN-KARUR-WEAVE-01","genset":"250kVA","hours":48}`
- `GET /plants/{id}/telemetry`

Docker:

```bash
docker build -t aeropure-twin .
docker run -p 8080:8080 aeropure-twin
```

## Replay numbers (250 kVA, 168 h)

See `data/sample_week_250kVA.json`:
- Capture 96.75%, CPCB compliance 98.8%
- Heat recovered 13,124 kWh-th (₹1.02 lakh)
- Carbon black 3.89 kg (honest: soot mass is small; heat + fine-shield dominate cash)
- Net ₹1.50 lakh / week duty, payback ~16 days at this load

## Judge one-liner

Japan already recovers heat. Europe already washes DPFs. The US even patented selling diesel soot. This twin packages all three cash flows on the **same Indian 250 kVA set**, with a replaceable harvest cartridge and a CPCB log a factory manager can hand to an inspector.

## Honest scope

- Validated against published order-of-magnitude numbers (BSFC, exhaust kg/kWh, DPF dP vs cake), **not** a specific OEM test cell.
- Carbon-black price assumes dried, bagged recovered soot sold as mid-grade pigment — not N330 virgin furnace black.
- Fine shield uses a 12% inspection-hit model x Rs 50k/day. Change the tariff in `aeropure/economics.py` for your SPCB circle.
