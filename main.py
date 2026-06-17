from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import uuid

# Package relative modular references
from app.models import EventRequest, ForecastResponse, PredictionsModel, DeploymentModel
from app.geo import create_impact_geojson, get_impact_radius_meters
from app.predict import ProductionPredictor

app = FastAPI(
    title="BTP Traffic Command API",
    description="Bengaluru Traffic Police - Predictive Event Management System",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global memory preservation instance tracking Aryan's saved file weights
ml_engine = ProductionPredictor("catboost_ensemble.pkl")

@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

@app.post("/api/v1/forecast", response_model=ForecastResponse)
def forecast_event(event: EventRequest):
    # Match the text feature format used during model training
    current_time_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    
    ml_input_payload = {
        "start_datetime": current_time_str,
        "event_cause": event.event_cause,
        "event_type": event.event_type,
        "corridor": event.corridor,
        "priority": event.priority
    }

    ml_output = ml_engine.predict_and_allocate(ml_input_payload)
    predicted_duration = ml_output["predicted_duration_minutes"]
    allocated_resources = ml_output["allocated_resources"]

    if predicted_duration > 120 and event.priority == "High":
        severity = "CRITICAL"
    elif predicted_duration > 90 or event.priority == "High":
        severity = "HIGH"
    elif predicted_duration > 45:
        severity = "MEDIUM"
    else:
        severity = "LOW"

    radius = get_impact_radius_meters(event.event_cause, event.requires_road_closure)
    geojson_data = create_impact_geojson(event.location.lat, event.location.lng, radius)

    diversion_map = {
        "Mysore Road": "Divert via Kanakapura Road",
        "Tumkur Road": "Divert via Magadi Road",
        "Bellary Road 1": "Divert via Hebbal Flyover",
        "Bellary Road 2": "Divert via Outer Ring Road North",
        "Hosur Road": "Divert via Sarjapur Road",
        "Magadi Road": "Divert via Chord Road",
        "ORR North 1": "Divert via NH-44",
        "ORR East 1": "Divert via Old Madras Road",
    }
    route = diversion_map.get(event.corridor, "Follow local traffic police directions")

    return ForecastResponse(
        event_id=f"BTP-{uuid.uuid4().hex[:6].upper()}",
        cause=event.event_cause,
        location=event.location,
        predictions=PredictionsModel(
            estimated_duration_mins=predicted_duration,
            severity_level=severity
        ),
        deployment_recommendation=DeploymentModel(
            traffic_cops_needed=allocated_resources["cops"],
            barricades=allocated_resources["barricades"],
            cranes=allocated_resources["cranes"],
            diversion_route=route
        ),
        spatial_impact_geojson=geojson_data
    )

@app.get("/api/v1/simulate")
def simulate_feed():
    return [
        {
            "event_id": "BTP-SIM01",
            "cause": "accident",
            "location": {
                "lat": 12.9716,
                "lng": 77.5946,
                "address": "MG Road, Bengaluru"
            },
            "predictions": {"estimated_duration_mins": 75.0, "severity_level": "MEDIUM"},
            "deployment_recommendation": {
                "traffic_cops_needed": 3,
                "barricades": 10,
                "cranes": 1,
                "diversion_route": "Follow local traffic police directions"
            }
        }
    ]