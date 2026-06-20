# ── Station Jurisdiction Capacity Table ──────────────────────────────────────
# Real BTP traffic stations have varying personnel/equipment strength.
# This caps what a single station can realistically deploy without backup.
STATION_CAPACITY = {
    "Peenya Police Station": {"max_cops": 12, "max_barricades": 30, "max_cranes": 1},
    "Yeshwanthpur Police Station": {"max_cops": 10, "max_barricades": 25, "max_cranes": 1},
    "Whitefield Police Station": {"max_cops": 14, "max_barricades": 35, "max_cranes": 2},
    "Koramangala Police Station": {"max_cops": 16, "max_barricades": 40, "max_cranes": 2},
    "Indiranagar Police Station": {"max_cops": 12, "max_barricades": 30, "max_cranes": 1},
    "Jayanagar Police Station": {"max_cops": 10, "max_barricades": 28, "max_cranes": 1},
    "Electronic City Police Station": {"max_cops": 14, "max_barricades": 32, "max_cranes": 2},
    "Silk Board Police Station": {"max_cops": 18, "max_barricades": 45, "max_cranes": 2},
    "HSR Layout Police Station": {"max_cops": 10, "max_barricades": 25, "max_cranes": 1},
    "Marathahalli Police Station": {"max_cops": 12, "max_barricades": 30, "max_cranes": 1},
}

# Fallback capacity for stations not in the table above
DEFAULT_CAPACITY = {"max_cops": 8, "max_barricades": 20, "max_cranes": 1}


def get_station_capacity(police_station: str) -> dict:
    """Looks up jurisdiction capacity for a given station.

    Falls back to a conservative default if the station is unrecognized,
    so the system never silently assumes unlimited capacity.
    """
    return STATION_CAPACITY.get(police_station, DEFAULT_CAPACITY)


def calculate_resources(
    duration_mins: float,
    priority: str,
    event_cause: str,
    requires_road_closure: bool,
    corridor: str,
    police_station: str = "Unknown",
) -> dict:
    
    # ── Standard Generic Station Capacity ────────────────────────────────
    # Instead of hardcoding names, we assume a baseline max capacity 
    # for ANY traffic station in the city.
    MAX_STATION_COPS = 12
    MAX_STATION_BARRICADES = 30
    MAX_STATION_CRANES = 1

    # Base Requirement (Standard Junction)
    cops = 2 
    barricades = 5
    cranes = 0

    # --- Realistic Duration Scaling ---
    if duration_mins > 240:
        cops += 4
        barricades += 15
    elif duration_mins > 120:
        cops += 3
        barricades += 10
    elif duration_mins > 60:
        cops += 1
        barricades += 5

    # --- Priority multiplier ---
    if priority == "High":
        cops = int(cops * 1.5)
        barricades = int(barricades * 1.3)

    # --- Realistic Event Rules ---
    if event_cause == "water_logging":
        cops += 4      # Needs manual traffic direction at bottlenecks
        barricades += 10
    elif event_cause in ["public_event", "procession", "protest"]:
        cops += 6      # Law & Order coordination
        barricades += 20
    elif event_cause == "construction":
        barricades += 15
    elif event_cause == "tree_fall":
        cops += 2
        barricades += 5
        cranes += 1
    elif event_cause in ["accident", "vehicle_breakdown"]:
        cops += 2
        cranes += 1

    # --- Road closure ---
    if requires_road_closure:
        barricades += 10
        cops += 2

    # --- Hard caps to prevent absurd numbers ---
    cops = min(cops, 20)
    barricades = min(barricades, 60)
    cranes = min(cranes, 3)

    # --- Severity label ---
    if duration_mins > 240 and priority == "High":
        severity = "CRITICAL"
    elif duration_mins > 120 or priority == "High":
        severity = "HIGH"
    elif duration_mins > 60:
        severity = "MEDIUM"
    else:
        severity = "LOW"

    # --- Dynamic Backup Logic ---
    # Compare the total needed vs the standard station capacity
    needs_backup = (
        cops > MAX_STATION_COPS or 
        barricades > MAX_STATION_BARRICADES or 
        cranes > MAX_STATION_CRANES
    )

    # What the primary station can actually provide
    station_cops = min(cops, MAX_STATION_COPS)
    station_barricades = min(barricades, MAX_STATION_BARRICADES)
    station_cranes = min(cranes, MAX_STATION_CRANES)

    return {
        "traffic_cops_needed": station_cops,
        "barricades": station_barricades,
        "cranes": station_cranes,
        "total_cops_required": cops,
        "total_barricades_required": barricades,
        "total_cranes_required": cranes,
        "severity": severity,
        "needs_backup": needs_backup,
        "responding_station": police_station, # Comes dynamically from KML in main.py
    }