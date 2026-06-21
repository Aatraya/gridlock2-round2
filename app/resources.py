# ── Station Jurisdiction Capacity Table ──────────────────────────────────────
# Real BTP traffic stations have varying personnel/equipment strength.
# This caps what a single station can realistically deploy without backup.
STATION_CAPACITY = {
    # --- Exact KML Outputs (Spatial Match) ---
    "Peenya PS": {"max_cops": 12, "max_barricades": 30, "max_cranes": 1},
    "Yeshwanthapura PS": {"max_cops": 10, "max_barricades": 25, "max_cranes": 1},
    "Whitefield PS": {"max_cops": 14, "max_barricades": 35, "max_cranes": 2},
    "Koramangala PS": {"max_cops": 16, "max_barricades": 40, "max_cranes": 2},
    "Indiranagar PS": {"max_cops": 12, "max_barricades": 30, "max_cranes": 1},
    "Jayanagar PS": {"max_cops": 10, "max_barricades": 28, "max_cranes": 1},
    "Electronic City PS": {"max_cops": 14, "max_barricades": 32, "max_cranes": 2},
    "H.S.R.Layout PS": {"max_cops": 10, "max_barricades": 28, "max_cranes": 1},
    "Madiwala PS": {"max_cops": 18, "max_barricades": 45, "max_cranes": 2}, 
    
    # --- Legacy Frontend Dropdown Formats (Manual Entry Match) ---
    "Peenya Police Station": {"max_cops": 12, "max_barricades": 30, "max_cranes": 1},
    "Yeshwanthpur Police Station": {"max_cops": 10, "max_barricades": 25, "max_cranes": 1},
    "Whitefield Police Station": {"max_cops": 14, "max_barricades": 35, "max_cranes": 2},
    "Koramangala Police Station": {"max_cops": 16, "max_barricades": 40, "max_cranes": 2},
    "Indiranagar Police Station": {"max_cops": 12, "max_barricades": 30, "max_cranes": 1},
    "Jayanagar Police Station": {"max_cops": 10, "max_barricades": 28, "max_cranes": 1},
    "Electronic City Police Station": {"max_cops": 14, "max_barricades": 32, "max_cranes": 2},
    "Silk Board Police Station": {"max_cops": 18, "max_barricades": 45, "max_cranes": 2},
    "HSR Layout Police Station": {"max_cops": 10, "max_barricades": 28, "max_cranes": 1},
}

# Global fallback defaults
MAX_STATION_COPS = 8
MAX_STATION_BARRICADES = 20
MAX_STATION_CRANES = 0

def calculate_resources(duration_mins, priority, event_cause, requires_road_closure, corridor, police_station):
    # --- 1. Base requirements ---
    cops = 2
    barricades = 2
    cranes = 0

    if duration_mins > 120:
        cops += 4
        barricades += 8
    elif duration_mins > 60:
        cops += 2
        barricades += 3

    # --- 2. Modifiers ---
    if priority == "High":
        cops += 4
        barricades += 5

    if event_cause in ["accident", "vehicle_breakdown", "tree_fall"]:
        cops += 2
        cranes += 1

    if requires_road_closure:
        barricades += 8
        cops += 2

    # --- 3. Safety Bounds ---
    cops = min(cops, 25)
    barricades = min(barricades, 30)
    cranes = min(cranes, 3)

    # --- 4. Severity Tagging ---
    if duration_mins > 240 and priority == "High":
        severity = "CRITICAL"
    elif duration_mins > 120 or priority == "High":
        severity = "HIGH"
    elif duration_mins > 60:
        severity = "MODERATE"
    else:
        severity = "LOW"

    # --- 5. JURISDICTION CAPACITY CHECK ---
    capacity = STATION_CAPACITY.get(
        police_station, 
        {"max_cops": MAX_STATION_COPS, "max_barricades": MAX_STATION_BARRICADES, "max_cranes": MAX_STATION_CRANES}
    )

    needs_backup = (
        cops > capacity["max_cops"] or 
        barricades > capacity["max_barricades"] or 
        cranes > capacity["max_cranes"]
    )

    # Cap deployment strictly to the exact station processing it
    station_cops = min(cops, capacity["max_cops"])
    station_barricades = min(barricades, capacity["max_barricades"])
    station_cranes = min(cranes, capacity["max_cranes"])

    # --- Simple diversion text (Day 4 baseline fallback) ---
    diversion_map = {
        "Mysore Road": "Divert via Kanakapura Road",
        "Tumkur Road": "Divert via Magadi Road",
        "Bellary Road 1": "Divert via Hebbal Flyover",
        "Bellary Road 2": "Divert via Outer Ring Road North",
        "Hosur Road": "Divert via Sarjapur Road",
        "Magadi Road": "Divert via Chord Road",
        "ORR North 1": "Divert via NH-44",
        "ORR East 1": "Divert via Old Madras Road",
        "Non-corridor": "Follow police directions",
    }
    diversion = diversion_map.get(corridor, "Follow local traffic police directions")

    return {
        "traffic_cops_needed": station_cops,
        "barricades": station_barricades,
        "cranes": station_cranes,
        "total_cops_required": cops,
        "total_barricades_required": barricades,
        "total_cranes_required": cranes,
        "needs_backup": needs_backup,
        "severity": severity,
        "responding_station": police_station,
        "diversion_route": diversion
    }