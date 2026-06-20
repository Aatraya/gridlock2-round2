import uuid
from datetime import datetime
from fastapi import FastAPI
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
    """Primary orchestrator endpoint.

    Accepts real-time incident notifications, runs predictive model
    forecasting, handles expert resource allocations constrained by the
    responding station's jurisdiction capacity, and generates dynamic
    geospatial bypass geometry lines.
    """
    # 1. Format a standardized UTC timestamp string to match training configurations
    current_time_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    # 2. Build the precise attribute dictionary schema required by predict.py
    ml_input_payload = {
        "start_datetime": current_time_str,
        "event_type": event.event_type,
        "event_cause": event.event_cause,
        "corridor": event.corridor,
        "priority": event.priority,
    }

    real_station_name = get_responding_station(
        event.location.lat, event.location.lng
    )

    # 3. Compute CatBoost clearance estimations and determine core rules numbers,
    #    constrained by the responding station's jurisdiction capacity
    ml_output = ml_engine.predict_and_allocate(
        input_data=ml_input_payload,
        requires_road_closure=event.requires_road_closure,
        police_station=real_station_name,
    )
    predicted_duration = ml_output["predicted_duration_minutes"]
    allocated_resources = ml_output["allocated_resources"]

    # 4. Map the continuous duration predictions into discrete priority alert levels
    if predicted_duration > 120 and event.priority == "High":
        severity = "CRITICAL"
    elif predicted_duration > 90 or event.priority == "High":
        severity = "HIGH"
    elif predicted_duration > 45:
        severity = "MEDIUM"
    else:
        severity = "LOW"

    # 5. Calculate spatial buffer impacts using proper geometric map projection metrics
    radius = get_impact_radius_meters(event.event_cause, event.requires_road_closure)
    geojson_data = create_impact_geojson(event.location.lat, event.location.lng, radius)

    # 6. DYNAMIC OSRM ROUTING LAYER
    route_text, route_geom = get_osrm_alternative_route(
        lat=event.location.lat,
        lng=event.location.lng,
        radius_meters=radius,  
    )

    # 7. Package everything into the verified structure contract to send to the UI
    return ForecastResponse(
        event_id=f"BTP-{uuid.uuid4().hex[:6].upper()}",
        cause=event.event_cause,
        location=event.location,
        predictions=PredictionsModel(
            estimated_duration_mins=predicted_duration, severity_level=severity
        ),
        deployment_recommendation=DeploymentModel(
            traffic_cops_needed=allocated_resources["traffic_cops_needed"],
            barricades=allocated_resources["barricades"],
            cranes=allocated_resources["cranes"],
            diversion_route=route_text,
            diversion_geometry=route_geom,
            total_cops_required=allocated_resources["total_cops_required"],
            total_barricades_required=allocated_resources["total_barricades_required"],
            total_cranes_required=allocated_resources["total_cranes_required"],
            needs_backup=allocated_resources["needs_backup"],
            responding_station=real_station_name,
        ),
        spatial_impact_geojson=geojson_data,
    )
