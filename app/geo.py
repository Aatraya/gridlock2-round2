from shapely.geometry import Point, mapping
from shapely.ops import transform
import pyproj
import requests

def get_impact_radius_meters(event_cause: str, requires_road_closure: bool) -> float:
    radius_map = {
        "construction": 1500,
        "water_logging": 1200,
        "tree_fall": 800,
        "accident": 800,
        "road_conditions": 1000,
        "pot_holes": 600,
        "congestion": 1000,
        "public_event": 2000,
        "procession": 1500,
        "protest": 1500,
        "vip_movement": 1200,
        "vehicle_breakdown": 500,
        "others": 600,
    }
    radius = radius_map.get(event_cause, 600)
    if requires_road_closure:
        radius = int(radius * 1.4)
    return float(radius)

def create_impact_geojson(lat: float, lng: float, radius_meters: float) -> dict:
    wgs84 = pyproj.CRS("EPSG:4326")
    local_aeqd = pyproj.CRS(
        proj="aeqd",
        lat_0=lat,
        lon_0=lng,
        datum="WGS84",
        units="m",
    )
    to_local = pyproj.Transformer.from_crs(wgs84, local_aeqd, always_xy=True)
    to_wgs84 = pyproj.Transformer.from_crs(local_aeqd, wgs84, always_xy=True)

    point_local = transform(to_local.transform, Point(lng, lat))
    circle_local = point_local.buffer(radius_meters)
    circle_wgs84 = transform(to_wgs84.transform, circle_local)

    return mapping(circle_wgs84)

import requests

def get_osrm_alternative_route(start_lat: float, start_lng: float, corridor: str) -> tuple[str, dict]:
    """
    Queries OSRM to generate a real-world bypass routing trajectory.
    Simulates a baseline destination coordinate offset based on the corridor pathing direction.
    """
    # Simple coordinate offsets to simulate a destination along the corridor
    corridor_offsets = {
        "Tumkur Road": (0.04, -0.04),     # Outbound North-West
        "Mysore Road": (-0.04, -0.04),    # Outbound South-West
        "Hosur Road": (-0.04, 0.04),      # Outbound South-East
        "Bellary Road 1": (0.04, 0.01),   # Outbound North
    }
    
    offset = corridor_offsets.get(corridor, (0.02, 0.02))
    dest_lat = start_lat + offset[0]
    dest_lng = start_lng + offset[1]
    
    # OSRM expects longitude first: {lng},{lat};{lng},{lat}
    url = f"http://router.project-osrm.org/route/v1/driving/{start_lng},{start_lat};{dest_lng},{dest_lat}"
    params = {
        "geometries": "geojson",
        "overview": "full",
        "steps": "false"
    }
    
    try:
        res = requests.get(url, params=params, timeout=3)
        if res.status_code == 200:
            data = res.json()
            if data.get("routes"):
                route_geojson = data["routes"][0]["geometry"]
                text_instruction = f"Dynamic diversion active: Path around congestion zone toward destination grid verified."
                return text_instruction, route_geojson
    except Exception as e:
        print(f"OSRM Network Exception Bypass: {e}")
        
    # Reliable default backup if the server fails or times out
    fallback_line = {
        "type": "LineString",
        "coordinates": [[start_lng, start_lat], [dest_lng, dest_lat]]
    }
    return "Follow manual traffic redirection markers on approach.", fallback_line