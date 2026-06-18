from pydantic import BaseModel, Field
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
    police_station: str = Field(..., alias="policeStation")
    location: LocationModel
    hour: Optional[int] = None
    dayofweek: Optional[int] = None

    class Config:
        populate_by_name = True

class PredictionsModel(BaseModel):
    estimated_duration_mins: float
    severity_level: str

class DeploymentModel(BaseModel):
    traffic_cops_needed: int
    barricades: int
    cranes: int
    diversion_route: str
    diversion_geometry: Optional[Any] = None

class ForecastResponse(BaseModel):
    event_id: str
    cause: str
    location: LocationModel
    predictions: PredictionsModel
    deployment_recommendation: DeploymentModel
    spatial_impact_geojson: Any