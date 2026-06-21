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

# Import schemas and models directly from models.py
from app.models import (
    DeploymentModel,
    EventRequest,
    ForecastResponse,
    PredictionsModel,
)
from app.predict import ProductionPredictor

# Initialize the main FastAPI application instance
app = FastAPI(
    title="BTP Traffic Command API",
    description="Bengaluru Traffic Police - Predictive Event Management System",
    version="1.0.0",
)

# Configure Cross-Origin Resource Sharing (CORS) middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load the CatBoost model pipeline into memory at application startup
ml_engine = ProductionPredictor("catboost_ensemble.pkl")


@app.get("/health")
def health():
    """Lightweight diagnostic health-check endpoint."""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.post("/api/v1/forecast", response_model=ForecastResponse)
def forecast_event(event: EventRequest):
    """Primary orchestrator endpoint."""
    try:
        # 1. Resolve Jurisdiction via KML if AUTO_ASSIGNED
        # Using .strip() to clean hidden newlines and spaces from KML raw text
        if event.police_station == "AUTO_ASSIGNED" or not event.police_station:
            real_station_name = get_responding_station(event.location.lat, event.location.lng).strip()
        else:
            real_station_name = event.police_station.strip()

        # 2. Build model payload map
        input_payload = {
            "event_type": event.event_type,
            "event_cause": event.event_cause,
            "corridor": event.corridor,
            "priority": event.priority,
            "hour_of_day": datetime.now(timezone.utc).hour,
            "day_of_week": datetime.now(timezone.utc).weekday(),
            "police_station": real_station_name
        }

        # 3. RUN PREDICTIVE FRAMEWORK WITH SPATIAL JURISDICTION
        prediction_results = ml_engine.predict_and_allocate(
            input_data=input_payload,
            police_station=real_station_name,  # Passes clean jurisdiction string to rules engine
            requires_road_closure=event.requires_road_closure
        )

        predicted_duration = prediction_results.get("predicted_duration_minutes", 60.0)
        allocated_resources = prediction_results.get("allocated_resources", {})
        severity = allocated_resources.get("severity", "MODERATE")

        # 4. Geospatial impact buffer
        radius = get_impact_radius_meters(event.event_cause, event.requires_road_closure)
        geojson_data = create_impact_geojson(event.location.lat, event.location.lng, radius)

        # 5. Dynamic OSRM Routing Layer
        route_text, route_geom = get_osrm_alternative_route(
            event.location.lat,
            event.location.lng,
            radius,
        )

        # 6. Package everything into the verified structure contract
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