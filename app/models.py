from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Any

class LocationModel(BaseModel):
    lat: float
    lng: float
    address: str

class EventRequest(BaseModel):
    event_cause: str = Field(..., alias="eventCause")
    event_type: str = Field(..., alias="eventType")
    priority: str
    corridor: str
    requires_road_closure: bool = Field(..., alias="requiresRoadClosure")
    police_station: Optional[str] = Field("AUTO_ASSIGNED", alias="policeStation")
    location: LocationModel

    model_config = ConfigDict(populate_by_name=True)

class PredictionsModel(BaseModel):
    estimated_duration_mins: float
    severity_level: str

class DeploymentModel(BaseModel):
    traffic_cops_needed: int
    barricades: int
    cranes: int
    diversion_route: str
    diversion_geometry: Optional[Any] = None
    # ── Jurisdiction capacity fields ──────────────────────────────────────
    total_cops_required: int = 0
    total_barricades_required: int = 0
    total_cranes_required: int = 0
    needs_backup: bool = False
    responding_station: str = "Unknown"

class ForecastResponse(BaseModel):
    event_id: str
    cause: str
    location: LocationModel
    predictions: PredictionsModel
    deployment_recommendation: DeploymentModel
    spatial_impact_geojson: Any
