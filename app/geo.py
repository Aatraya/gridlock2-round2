from shapely.geometry import Point, mapping
from shapely.ops import transform
import pyproj
import requests
import geopandas as gpd
from shapely.geometry import Point
import fiona
import pandas as pd

# Explicitly enable both standard and extended KML drivers
fiona.drvsupport.supported_drivers['KML'] = 'rw'
fiona.drvsupport.supported_drivers['LIBKML'] = 'rw'

# Load the file once at startup
try:
    # Ensure the file is renamed to this exact string on the server
    JURISDICTIONS_GDF = gpd.read_file('blr_police.kml', driver='KML')
    print(f"SUCCESS: Loaded {len(JURISDICTIONS_GDF)} Police Jurisdictions.")
    print(f"Available KML Columns: {JURISDICTIONS_GDF.columns.tolist()}")
except Exception as e:
    print(f"CRITICAL WARNING: KML File failed to load! Error: {e}")
    JURISDICTIONS_GDF = None

def get_responding_station(lat: float, lng: float) -> str:
    """
    Performs a Point-in-Polygon spatial join to find the exact legal jurisdiction.
    """
    if JURISDICTIONS_GDF is None or JURISDICTIONS_GDF.empty:
        return "Nearest Available Station" # Fallback if file failed to load
        
    incident_point = Point(lng, lat)
    
    # Iterate through the polygons to find the coordinate match
    for idx, row in JURISDICTIONS_GDF.iterrows():
        if row['geometry'].contains(incident_point):
            
            # Check for the custom BTP schema attribute first
            if 'PS_BOUNDName' in row and pd.notna(row['PS_BOUNDName']):
                return str(row['PS_BOUNDName']).title() + " Traffic PS"
                
            # Fallback to standard KML Name tag
            if 'Name' in row and pd.notna(row['Name']):
                return str(row['Name']).title() + " Traffic PS"
                
            return "Local Traffic Station"
            
    return "Out of Jurisdiction / Highway Patrol"

def get_impact_radius_meters(event_cause: str, requires_road_closure: bool) -> float:
    radius_map = {
        "construction": 400,  # Blocks 1-2 intersections
        "water_logging": 500,  # E.g., Silk Board underpass flooding
        "tree_fall": 150,  # Localized to one stretch/signal
        "accident": 250,  # Rubbernecking + lane blockage
        "road_conditions": 300,  # Ongoing slow-downs
        "pot_holes": 50,  # Highly localized speed bump effect
        "congestion": 800,  # Heavy rolling queues (e.g., Hebbal)
        "public_event": 1000,  # Chinnaswamy stadium matches
        "procession": 600,  # Moving blockages
        "protest": 600,  # Freedom park standard radius
        "vip_movement": 1000,  # VIP rolling blocks affect large grids
        "vehicle_breakdown": 100,  # 1 lane blocked
        "others": 200,
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


def get_osrm_alternative_route(
    lat: float, lng: float, radius_meters: float
) -> tuple[str, dict]:
    """
    City-agnostic dynamic routing.
    Calculates a detour path across the impact zone using pure geometric offsets.
    """
    # 1 degree of latitude is roughly 111,000 meters.
    # We set the start/end points 1.5x the radius away from the epicenter.
    offset_deg = (radius_meters * 1.5) / 111000.0

    start_lat = lat - offset_deg
    start_lng = lng - offset_deg
    dest_lat = lat + offset_deg
    dest_lng = lng + offset_deg

    url = f"http://router.project-osrm.org/route/v1/driving/{start_lng},{start_lat};{dest_lng},{dest_lat}"
    params = {
        "geometries": "geojson",
        "overview": "full",
        "steps": "true",  # Extracts real street names
    }

    try:
        res = requests.get(url, params=params, timeout=5)
        if res.status_code == 200:
            data = res.json()
            if data.get("routes"):
                route = data["routes"][0]
                route_geojson = route["geometry"]

                # Extract dynamic street names for ANY city
                street_names = []
                for leg in route.get("legs", []):
                    for step in leg.get("steps", []):
                        name = step.get("name")
                        if name and name not in street_names and "Unnamed" not in name:
                            street_names.append(name)

                if street_names:
                    top_streets = ", ".join(street_names[:3])
                    return (
                        f"Dynamic Diversion Active: Reroute traffic via {top_streets}.",
                        route_geojson,
                    )
                return (
                    "Dynamic Diversion Active: Follow calculated parallel route.",
                    route_geojson,
                )
    except Exception as e:
        print(f"OSRM Error: {e}")

    # Fallback straight line
    fallback = {
        "type": "LineString",
        "coordinates": [[start_lng, start_lat], [dest_lng, dest_lat]],
    }
    return "Follow local traffic police redirection markers.", fallback
