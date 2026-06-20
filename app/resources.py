def calculate_resources(
    duration_mins: float,
    priority: str,
    event_cause: str,
    requires_road_closure: bool,
    corridor: str,
) -> dict:
    """Rule-based expert system.

    Takes ML prediction + event metadata → deployment recommendation.
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

    # --- Hard caps so we don't suggest 10,000 cops ---
    cops = min(cops, 30)
    barricades = min(barricades, 80)
    cranes = min(cranes, 3)

    # --- Severity label ---
    if duration_mins > 300 and priority == "High":
        severity = "CRITICAL"
    elif duration_mins > 120 or priority == "High":
        severity = "HIGH"
    elif duration_mins > 60:
        severity = "MEDIUM"
    else:
        severity = "LOW"

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
    # FIXED: Querying using corridor instead of event_cause to avoid broken defaults
    diversion = diversion_map.get(corridor, "Follow local traffic police directions")

    return {
        "traffic_cops_needed": cops,
        "barricades": barricades,
        "cranes": cranes,
        "severity": severity,
        "diversion_route": diversion,
    }