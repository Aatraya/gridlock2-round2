import uuid
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.geo import (
    create_impact_geojson,
    get_impact_radius_meters,
    get_osrm_alternative_route,
    get_responding_station,
)
from app.models import (
    DeploymentModel,
    EventRequest,
    ForecastResponse,
    PredictionsModel,
)
from app.predict import ProductionPredictor

app = FastAPI(
    title="BTP Traffic Command API",
    description="Bengaluru Traffic Police - Predictive Event Management System",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

ml_engine = ProductionPredictor("catboost_ensemble.pkl")


@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.post("/api/v1/forecast", response_model=ForecastResponse)
def forecast_event(event: EventRequest):
    try:
        # 1. Resolve Jurisdiction via Point-In-Polygon KML Search
        if not event.police_station or event.police_station.strip().upper() == "AUTO_ASSIGNED":
            real_station_name = get_responding_station(event.location.lat, event.location.lng)
        else:
            real_station_name = event.police_station.strip()

        # 2. Extract Predictive Parameters and Evaluation Radius
        radius = get_impact_radius_meters(event.event_cause, event.priority)
        geojson_data = create_impact_geojson(event.location.lat, event.location.lng, radius)

        # 3. Call Machine Learning Prediction Engine and Resource Manager
        features = {
            "event_cause": event.event_cause,
            "priority": event.priority,
            "corridor": event.corridor,
            "latitude": event.location.lat,
            "longitude": event.location.lng,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        predicted_duration, severity, allocated_resources = ml_engine.predict_and_allocate(
            features, real_station_name
        )

        # 4. Compute Dynamic OSRM Route Geometry
        route_text, route_geom = get_osrm_alternative_route(
            event.location.lat,
            event.location.lng,
            radius,
        )

        return ForecastResponse(
            event_id=f"BTP-{uuid.uuid4().hex[:6].upper()}",
            cause=event.event_cause,
            location=event.location,
            predictions=PredictionsModel(
                estimated_duration_mins=predicted_duration, severity_level=severity
            ),
            deployment_recommendation=DeploymentModel(
                traffic_cops_needed=allocated_resources.get("traffic_cops_needed", 0),
                barricades=allocated_resources.get("barricades", 0),
                cranes=allocated_resources.get("cranes", 0),
                diversion_route=route_text,
                diversion_geometry=route_geom,
                total_cops_required=allocated_resources.get("total_cops_required", 0),
                total_barricades_required=allocated_resources.get("total_barricades_required", 0),
                total_cranes_required=allocated_resources.get("total_cranes_required", 0),
                needs_backup=allocated_resources.get("needs_backup", False),
                responding_station=real_station_name,
            ),
            spatial_impact_geojson=geojson_data,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))