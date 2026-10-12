"""Places for the map: a task's own coordinates when it has them, else the centre of its city."""

from __future__ import annotations

# "City, ST" -> (lat, lng). The cities the catalogue uses. Add a city here when a task names a new one.
CITY_COORDS: dict[str, tuple[float, float]] = {
    "Austin, TX": (30.2672, -97.7431), "Dallas, TX": (32.7767, -96.7970), "Houston, TX": (29.7604, -95.3698), "San Antonio, TX": (29.4241, -98.4936),
    "Chicago, IL": (41.8781, -87.6298), "New York, NY": (40.7128, -74.0060), "Brooklyn, NY": (40.6782, -73.9442), "Boston, MA": (42.3601, -71.0589),
    "Philadelphia, PA": (39.9526, -75.1652), "Washington, DC": (38.9072, -77.0369), "Atlanta, GA": (33.7490, -84.3880), "Miami, FL": (25.7617, -80.1918),
    "Miami Beach, FL": (25.7907, -80.1300), "Orlando, FL": (28.5383, -81.3792), "Charlotte, NC": (35.2271, -80.8431), "Raleigh, NC": (35.7796, -78.6382),
    "Nashville, TN": (36.1627, -86.7816), "Denver, CO": (39.7392, -104.9903), "Phoenix, AZ": (33.4484, -112.0740), "Tucson, AZ": (32.2226, -110.9747),
    "Albuquerque, NM": (35.0844, -106.6504), "Las Vegas, NV": (36.1699, -115.1398), "Salt Lake City, UT": (40.7608, -111.8910), "Boise, ID": (43.6150, -116.2023),
    "Seattle, WA": (47.6062, -122.3321), "Portland, OR": (45.5152, -122.6784), "San Francisco, CA": (37.7749, -122.4194), "Oakland, CA": (37.8044, -122.2712),
    "San Jose, CA": (37.3382, -121.8863), "Los Angeles, CA": (34.0522, -118.2437), "San Diego, CA": (32.7157, -117.1611), "Sacramento, CA": (38.5816, -121.4944),
    "Minneapolis, MN": (44.9778, -93.2650), "Bloomington, MN": (44.8408, -93.2983), "Madison, WI": (43.0731, -89.4012), "Milwaukee, WI": (43.0389, -87.9065),
    "Detroit, MI": (42.3314, -83.0458), "Columbus, OH": (39.9612, -82.9988), "Cleveland, OH": (41.4993, -81.6944), "Pittsburgh, PA": (40.4406, -79.9959),
    "St. Louis, MO": (38.6270, -90.1994), "Kansas City, MO": (39.0997, -94.5786), "Indianapolis, IN": (39.7684, -86.1581), "Baltimore, MD": (39.2904, -76.6122),
    "New Orleans, LA": (29.9511, -90.0715), "Oklahoma City, OK": (35.4676, -97.5164), "Omaha, NE": (41.2565, -95.9345), "Honolulu, HI": (21.3069, -157.8583),
    "Anchorage, AK": (61.2181, -149.9003),
}


def place_of(location: str | None, payload: dict | None) -> dict | None:
    """{lat, lng, exact} for a task, or None when it can be done from anywhere."""
    geo = (payload or {}).get("geo")
    if isinstance(geo, dict) and isinstance(geo.get("lat"), int | float) and isinstance(geo.get("lng"), int | float):
        return {"lat": float(geo["lat"]), "lng": float(geo["lng"]), "exact": True}
    if location and location in CITY_COORDS:
        lat, lng = CITY_COORDS[location]
        return {"lat": lat, "lng": lng, "exact": False}
    return None


def maps_url(place: dict | None, location: str | None) -> str | None:
    """A link that opens the place in the phone's map app."""
    if place and place["exact"]:
        return f"https://www.google.com/maps/search/?api=1&query={place['lat']:.6f},{place['lng']:.6f}"
    if location and location != "Remote":
        return "https://www.google.com/maps/search/?api=1&query=" + location.replace(" ", "+")
    return None
