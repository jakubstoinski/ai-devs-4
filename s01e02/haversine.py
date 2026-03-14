import math


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance in kilometres between two points on Earth.

    Args:
        lat1: Latitude of point 1 in decimal degrees
        lon1: Longitude of point 1 in decimal degrees
        lat2: Latitude of point 2 in decimal degrees
        lon2: Longitude of point 2 in decimal degrees

    Returns:
        Distance in kilometres
    """
    R = 6371.0  # Earth radius in km

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def find_closest_power_plant(name: str, surname: str, person_locations: list[dict], power_plants: list[dict]) -> dict:
    """Find the closest power plant to any of a person's spotted locations.

    Args:
        name: Person's first name.
        surname: Person's last name.
        person_locations: List of {"lat": float, "lon": float} dicts for the person's locations.
        power_plants: List of {"code": str, "lat": float, "lon": float} dicts for active power plants.

    Returns:
        {"name": str, "surname": str, "code": str, "distance_km": float} of the closest power plant.
    """
    best = None
    for loc in person_locations:
        for plant in power_plants:
            dist = haversine_km(loc["lat"], loc["lon"], plant["lat"], plant["lon"])
            if best is None or dist < best["distance_km"]:
                best = {"name": name, "surname": surname, "code": plant["code"], "distance_km": round(dist, 3)}
    return best


FIND_CLOSEST_POWER_PLANT_TOOL = {
    "type": "function",
    "function": {
        "name": "find_closest_power_plant",
        "description": (
            "Given a person's name, surname, their spotted locations, and a list of active power plant coordinates, "
            "calculates all pairwise distances and returns the person's name, surname, closest power plant code, and distance."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Person's first name"},
                "surname": {"type": "string", "description": "Person's last name"},
                "person_locations": {
                    "type": "array",
                    "description": "List of spotted locations for the person.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "lat": {"type": "number", "description": "Latitude in decimal degrees"},
                            "lon": {"type": "number", "description": "Longitude in decimal degrees"},
                        },
                        "required": ["lat", "lon"],
                    },
                },
                "power_plants": {
                    "type": "array",
                    "description": "List of active power plants with their coordinates and codes.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "code": {"type": "string", "description": "Power plant code e.g. PWR1234PL"},
                            "lat": {"type": "number", "description": "Latitude in decimal degrees"},
                            "lon": {"type": "number", "description": "Longitude in decimal degrees"},
                        },
                        "required": ["code", "lat", "lon"],
                    },
                },
            },
            "required": ["name", "surname", "person_locations", "power_plants"],
        },
    },
}


if __name__ == "__main__":
    # Example: distance between Warsaw and Kraków
    dist = haversine_km(52.2297, 21.0122, 50.0647, 19.9450)
    print(f"Warsaw -> Kraków: {dist:.1f} km")