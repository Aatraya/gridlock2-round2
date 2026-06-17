from shapely.geometry import Point, mapping
from shapely.ops import transform
import pyproj

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