import math

# --- Station Jurisdiction Capacity Table ---
# Maps normalized keys securely to prevent fallback penalties.
STATION_CAPACITY = {
    "PEENYA PS": {"max_cops": 12, "max_barricades": 30, "max_cranes": 1},
    "YESHWANTHAPURA PS": {"max_cops": 10, "max_barricades": 25, "max_cranes": 1},
    "WHITEFIELD PS": {"max_cops": 14, "max_barricades": 35, "max_cranes": 2},
    "KORAMANGALA PS": {"max_cops": 16, "max_barricades": 40, "max_cranes": 2},
    "INDIRANAGAR PS": {"max_cops": 12, "max_barricades": 30, "max_cranes": 1},
    "JAYANAGAR PS": {"max_cops": 10, "max_barricades": 28, "max_cranes": 1},
    "ELECTRONIC CITY PS": {"max_cops": 14, "max_barricades": 32, "max_cranes": 2},
    "HSR LAYOUT PS": {"max_cops": 10, "max_barricades": 28, "max_cranes": 1},
    "MADIWALA PS": {"max_cops": 18, "max_barricades": 45, "max_cranes": 2},
    "HULIMAVU PS": {"max_cops": 10, "max_barricades": 28, "max_cranes": 1},
    "BANASHANKARI PS": {"max_cops": 14, "max_barricades": 35, "max_cranes": 1},
    "BASAVANGUDI PS": {"max_cops": 12, "max_barricades": 30, "max_cranes": 1},
    "HEBBAL PS": {"max_cops": 10, "max_barricades": 25, "max_cranes": 1},
    "R T NAGAR PS": {"max_cops": 12, "max_barricades": 30, "max_cranes": 1},
    "VIJAYANAGARA PS": {"max_cops": 12, "max_barricades": 30, "max_cranes": 1},
    "CUBBON PARK PS": {"max_cops": 15, "max_barricades": 35, "max_cranes": 1},
    "ASHOKNAGAR PS": {"max_cops": 14, "max_barricades": 30, "max_cranes": 1},
    "ULSOOR GATE PS": {"max_cops": 15, "max_barricades": 35, "max_cranes": 2},
}

def normalize_station_name(raw_name: str) -> str:
    """
    Normalizes spatial KML text and legacy dropdown strings to match dictionary capacities.
    """
    if not raw_name:
        return "DEFAULT PS"
    
    clean = str(raw_name).upper().strip()
    
    # Structural string cleaning
    clean = clean.replace("POLICE STATION", "PS").replace("TRAFFIC", "").replace("PS PS", "PS")
    clean = clean.replace(".", " ").replace("-", " ")
    
    # Keyword anchor matching
    if "YESHWANTH" in clean or "RMC YARD" in clean:
        return "YESHWANTHAPURA PS"
    if "HULIMAVU" in clean:
        return "HULIMAVU PS"
    if "PEENYA" in clean:
        return "PEENYA PS"
    if "WHITEFIELD" in clean:
        return "WHITEFIELD PS"
    if "KORAMANGALA" in clean:
        return "KORAMANGALA PS"
    if "INDIRANAGAR" in clean:
        return "INDIRANAGAR PS"
    if "JAYANAGAR" in clean:
        return "JAYANAGAR PS"
    if "ELECTRONIC" in clean:
        return "ELECTRONIC CITY PS"
    if "HSR" in clean or "H S R" in clean:
        return "HSR LAYOUT PS"
    if "MADIWALA" in clean:
        return "MADIWALA PS"
    if "BANASHANKARI" in clean:
        return "BANASHANKARI PS"
    if "BASAVANGUDI" in clean:
        return "BASAVANGUDI PS"
    if "HEBBAL" in clean:
        return "HEBBAL PS"
    if "VIJAYANAGAR" in clean:
        return "VIJAYANAGARA PS"
    if "CUBBON" in clean:
        return "CUBBON PARK PS"
    
    # Generic safety formatting if no specific anchor matches
    if not clean.endswith("PS"):
        clean += " PS"
    return " ".join(clean.split())

def calculate_resources(duration_mins: float, priority: str, event_cause: str, police_station: str, corridor: str = "Non-corridor") -> dict:
    """
    Calculates exact required resource allocations and verifies local capacity limits.
    """
    # Base configuration allocations
    if priority == "High":
        base_cops = 6
        base_barricades = 12
    elif priority == "Medium":
        base_cops = 4
        base_barricades = 6
    else:
        base_cops = 2
        base_barricades = 4

    # Scale allocation linearly with incident duration
    duration_multiplier = max(1.0, duration_mins / 60.0)
    cops = math.ceil(base_cops * duration_multiplier)
    barricades = math.ceil(base_barricades * (1.0 + (duration_multiplier - 1.0) * 0.5))
    
    cranes = 0
    if event_cause in ["accident", "breakdown", "water_logging"]:
        cranes = 1 if priority in ["Medium", "High"] else 0

    # Clean the input station string to find the valid constraint mapping
    normalized_key = normalize_station_name(police_station)
    capacity = STATION_CAPACITY.get(
        normalized_key, 
        {"max_cops": 15, "max_barricades": 30, "max_cranes": 1} # Realistic baseline fallback
    )

    # Compute status threshold flags
    needs_backup = (
        cops > capacity["max_cops"] or 
        barricades > capacity["max_barricades"] or 
        cranes > capacity["max_cranes"]
    )

    station_cops = min(cops, capacity["max_cops"])
    station_barricades = min(barricades, capacity["max_barricades"])
    station_cranes = min(cranes, capacity["max_cranes"])

    return {
        "traffic_cops_needed": station_cops,
        "barricades": station_barricades,
        "cranes": station_cranes,
        "total_cops_required": cops,
        "total_barricades_required": barricades,
        "total_cranes_required": cranes,
        "needs_backup": needs_backup
    }