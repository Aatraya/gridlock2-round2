# BTP Traffic Command API

Predictive backend for the **Bengaluru Traffic Police Event-Driven Congestion** problem statement (Flipkart Grid 2.0 — Round 2).

Given a traffic-affecting event (accident, construction, tree fall, rally, etc.), the API forecasts how long it will disrupt traffic, recommends manpower and barricading, calculates the spatial impact zone, and generates a real road-network diversion route.

---

## Problem statement

> How can historical and real-time data be used to forecast event-related traffic impact and recommend optimal manpower, barricading, and diversion plans?

This service answers all three asks:

| Ask | Component |
|---|---|
| Forecast traffic impact | CatBoost ensemble model trained on historical event data |
| Recommend manpower & barricading | Rule-based expert system (`resources.py`) |
| Recommend diversion plans | Live OSRM routing around the impact zone (`geo.py`) |

---

## Architecture

```
btp-backend/
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI app, orchestrates the full pipeline
│   ├── models.py        # Pydantic request/response schemas
│   ├── predict.py        # Loads CatBoost ensemble, runs inference
│   ├── geo.py             # Impact-zone polygon + OSRM diversion routing
│   └── resources.py     # Expert-system rules: cops, barricades, cranes, severity
├── catboost_ensemble.pkl  # Trained model artifact (Aryan's pipeline)
├── requirements.txt
└── run.py                 # Entry point
```

### Request flow

```
Frontend POST /api/v1/forecast
        │
        ▼
EventRequest validated (Pydantic)
        │
        ▼
ProductionPredictor.predict_and_allocate()
   ├─ Builds feature row: event_cause, corridor, priority, hour_of_day, day_of_week
   ├─ Runs CatBoost ensemble → log-duration → expm1 → predicted_duration_minutes
   └─ Calls calculate_resources() → cops, barricades, cranes, severity
        │
        ▼
get_impact_radius_meters() + create_impact_geojson()
   └─ Azimuthal equidistant projection → accurate circular buffer in meters
        │
        ▼
get_osrm_alternative_route()
   └─ Live OSRM query → real road-network diversion path (GeoJSON LineString)
        │
        ▼
ForecastResponse returned to frontend
```

---

## Setup

### Prerequisites
- Python 3.10+
- `catboost_ensemble.pkl` placed in the project root (provided by the ML pipeline)

### Installation

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Run

```bash
python run.py
```

Server starts at `http://localhost:8000`. Interactive API docs at `http://localhost:8000/docs`.

---

## API

### `GET /health`
Lightweight liveness check.

```json
{ "status": "ok", "timestamp": "2026-06-20T10:32:00" }
```

### `POST /api/v1/forecast`

**Request**
```json
{
  "eventCause": "accident",
  "eventType": "unplanned",
  "priority": "High",
  "corridor": "Tumkur Road",
  "requiresRoadClosure": true,
  "policeStation": "Peenya Police Station",
  "location": {
    "lat": 13.0285,
    "lng": 77.5195,
    "address": "Near Peenya Metro Station, Tumkur Road"
  }
}
```

**Response**
```json
{
  "event_id": "BTP-850BD1",
  "cause": "accident",
  "location": { "lat": 13.0285, "lng": 77.5195, "address": "..." },
  "predictions": {
    "estimated_duration_mins": 70.9,
    "severity_level": "HIGH"
  },
  "deployment_recommendation": {
    "traffic_cops_needed": 10,
    "barricades": 24,
    "cranes": 1,
    "diversion_route": "Divert via Magadi Road",
    "diversion_geometry": { "type": "LineString", "coordinates": [...] }
  },
  "spatial_impact_geojson": { "type": "Polygon", "coordinates": [...] }
}
```

Note: the request schema accepts camelCase keys (`eventCause`, `requiresRoadClosure`, etc.) via Pydantic aliases, matching the frontend's native JSON convention — no transformation needed on either side of the handshake.

---

## Design notes

**Model features.** The CatBoost ensemble was trained on exactly five columns: `event_cause`, `corridor`, `priority`, `hour_of_day`, `day_of_week`. `predict.py` reads the feature list directly from the model artifact at load time and builds the inference row in that exact order — this guards against silent schema drift if the model is retrained with a different feature set.

**Spatial impact zone.** The "impact radius" is a circular buffer sized by event cause (construction = 1500m, breakdown = 500m, etc.) and widened 40% if a road closure is in effect. It is generated using a local azimuthal equidistant projection centered on the event, so the circle is geometrically accurate in meters rather than distorted by latitude-dependent longitude scaling.

**Diversion routing.** Unlike the impact zone, the diversion path is not a static lookup — it queries the public OSRM routing engine live and returns a real road-network path as a GeoJSON `LineString`. If OSRM is unreachable, it falls back to a straight-line path so the endpoint never hard-fails.

**Resource allocation.** `resources.py` is a single source of truth used identically by both the live-prediction path and the model-unavailable fallback path, so manpower recommendations stay consistent regardless of whether the ML model loaded successfully. All outputs are hard-capped (max 30 cops, 80 barricades, 3 cranes) to avoid degenerate recommendations on extreme predicted durations.

---

## Known simplifications (by design, not oversight)

- **Impact zone is a circle, not a road-network isochrone.** Isochrones (true drivable-distance polygons) were considered but deprioritized in favor of investing the available time in real OSRM-based diversion routing, since drivers and dispatchers act on the diversion path, not the shape of the impact zone.
- **No live traffic feed integration.** The problem statement asks for forecasting from historical and real-time *event* data (i.e. the incoming event report), not live sensor/GPS congestion feeds. The model is intentionally a decision-support forecaster, not an autonomous live-traffic system.
- **No post-event feedback loop.** Predicted vs. actual duration is not currently logged or used to retrain — a natural next step beyond hackathon scope.

---

## Team

- **Geospatial & Backend** — Aatraya Mukherjee
- **ML / Predictive Engine** — Aryan
- **Frontend** — Amogh Gurudatta

Built for Flipkart Grid 2.0, Round 2.
