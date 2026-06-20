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
    """Rule-based expert system.

    Takes ML prediction + event metadata → deployment recommendation,
    constrained by the responding station's actual jurisdiction capacity.
    """

    cops = 2
    barricades = 5
    cranes = 0

    # --- Base rules on duration ---
    if duration_mins > 300:
        cops += 6
        barricades += 20
    elif duration_mins > 120:
        cops += 4
        barricades += 12
    elif duration_mins > 60:
        cops += 2
        barricades += 6
    else:
        cops += 1
        barricades += 2

    # --- Priority multiplier ---
    if priority == "High":
        cops = int(cops * 1.5)
        barricades = int(barricades * 1.3)

    # --- Event-cause specific rules ---
    if event_cause in ["construction", "road_conditions"]:
        barricades += 10
        cranes = 1
    elif event_cause == "tree_fall":
        cranes = 1
        barricades += 4
    elif event_cause in ["accident"]:
        cops += 2
        cranes = 1
    elif event_cause in ["public_event", "procession", "protest"]:
        cops += 4
        barricades += 15
    elif event_cause == "water_logging":
        barricades += 8

    # --- Road closure adds more barricades ---
    if requires_road_closure:
        barricades += 10
        cops += 2

    # --- Hard global caps so we don't suggest 10,000 cops ---
    cops = min(cops, 30)
    barricades = min(barricades, 80)
    cranes = min(cranes, 3)

    # --- Severity label (computed BEFORE jurisdiction capping, since
    #     severity reflects the actual scale of the event, not what one
    #     station can supply) ---
    if duration_mins > 300 and priority == "High":
        severity = "CRITICAL"
    elif duration_mins > 120 or priority == "High":
        severity = "HIGH"
    elif duration_mins > 60:
        severity = "MEDIUM"
    else:
        severity = "LOW"

    # --- Jurisdiction capacity check ---
    capacity = get_station_capacity(police_station)
    needs_backup = (
        cops > capacity["max_cops"]
        or barricades > capacity["max_barricades"]
        or cranes > capacity["max_cranes"]
    )

    # Cap the recommendation to what this specific station can deploy.
    # The "needed" totals are preserved separately so the dispatch order
    # can show both numbers if backup is required.
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
        "responding_station": police_station,
        "severity": severity,
        "diversion_route": diversion,
    }
