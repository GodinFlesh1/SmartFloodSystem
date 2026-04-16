"""
Safe route and shelter service.
- Finds nearest safe shelters using OpenStreetMap Overpass API (free, no key)
- Calculates driving/walking route using OpenRouteService API
"""

import os
import httpx
from typing import Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()

ORS_BASE     = "https://api.openrouteservice.org"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

SHELTER_QUERY = """
[out:json][timeout:25];
(
  node["amenity"="community_centre"](around:{radius},{lat},{lon});
  node["amenity"="school"](around:{radius},{lat},{lon});
  node["amenity"="hospital"](around:{radius},{lat},{lon});
  node["amenity"="place_of_worship"](around:{radius},{lat},{lon});
  node["building"="civic"](around:{radius},{lat},{lon});
  node["emergency"="assembly_point"](around:{radius},{lat},{lon});
);
out body;
"""


class RouteService:

    async def get_safe_places(
        self, lat: float, lon: float, radius_m: int = 5000
    ) -> List[Dict]:
        query = SHELTER_QUERY.format(lat=lat, lon=lon, radius=radius_m)

        async with httpx.AsyncClient(timeout=20) as client:
            try:
                resp = await client.post(OVERPASS_URL, data={"data": query})
                resp.raise_for_status()
                elements = resp.json().get("elements", [])
            except Exception:
                return []

        places = []
        for el in elements:
            tags      = el.get("tags", {})
            name      = (tags.get("name")
                         or tags.get("amenity", "").replace("_", " ").title()
                         or "Safe Place")
            place_lat = el.get("lat")
            place_lon = el.get("lon")
            if not place_lat or not place_lon:
                continue

            dist = _haversine(lat, lon, place_lat, place_lon)
            amenity = tags.get("amenity", tags.get("building", "shelter"))

            places.append({
                "name":       name,
                "type":       amenity,
                "latitude":   place_lat,
                "longitude":  place_lon,
                "distance_m": round(dist * 1000),
                "distance_km": round(dist, 2),
                "address":    tags.get("addr:street", ""),
            })

        places.sort(key=lambda x: x["distance_m"])
        return places[:10]

    async def get_route(
        self,
        from_lat: float, from_lon: float,
        to_lat: float,   to_lon: float,
        profile: str = "driving-car",
    ) -> Dict:
        ors_key = os.getenv("ORS_API_KEY", "")
        if not ors_key:
            return {"success": False, "error": "ORS API key not configured"}

        headers = {
            "Authorization": ors_key,
            "Content-Type":  "application/json",
        }
        body = {
            "coordinates": [
                [from_lon, from_lat],
                [to_lon,   to_lat],
            ],
            "instructions":        True,
            "instructions_format": "text",
            "language":            "en",
            "units":               "m",
        }

        url = f"{ORS_BASE}/v2/directions/{profile}"

        async with httpx.AsyncClient(timeout=20) as client:
            try:
                resp = await client.post(url, json=body, headers=headers)
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPStatusError as e:
                return {"success": False, "error": f"ORS error {e.response.status_code}"}
            except Exception as e:
                return {"success": False, "error": str(e)}

        try:
            route   = data["routes"][0]
            summary = route["summary"]
            steps   = []
            for seg in route.get("segments", []):
                for step in seg.get("steps", []):
                    steps.append({
                        "instruction": step.get("instruction", ""),
                        "distance_m":  round(step.get("distance", 0)),
                        "duration_s":  round(step.get("duration", 0)),
                    })

            # Decode geometry (encoded polyline) to lat/lon list
            coords = _decode_polyline(route["geometry"])

            return {
                "success":      True,
                "distance_m":   round(summary["distance"]),
                "duration_s":   round(summary["duration"]),
                "distance_km":  round(summary["distance"] / 1000, 2),
                "duration_min": round(summary["duration"] / 60),
                "coordinates":  coords,  # [[lat,lon], ...]
                "steps":        steps,
                "profile":      profile,
            }
        except (KeyError, IndexError) as e:
            return {"success": False, "error": f"Could not parse route: {e}"}

    async def get_safe_route_to_shelter(
        self,
        lat: float, lon: float,
        radius_m: int = 5000,
        profile: str = "driving-car",
    ) -> Dict:
        places = await self.get_safe_places(lat, lon, radius_m)

        if not places:
            return {
                "success": False,
                "error":   "No safe shelters found within radius.",
                "all_shelters": [],
            }

        nearest = places[0]
        route   = await self.get_route(
            from_lat=lat,               from_lon=lon,
            to_lat=nearest["latitude"], to_lon=nearest["longitude"],
            profile=profile,
        )

        return {
            "success":      route.get("success", False),
            "shelter":      nearest,
            "all_shelters": places,
            "route":        route,
            "error":        route.get("error"),
        }


def _haversine(lat1, lon1, lat2, lon2) -> float:
    from math import radians, cos, sin, asin, sqrt
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 6371 * 2 * asin(sqrt(a))


def _decode_polyline(encoded: str) -> List[List[float]]:
    """Decode Google/ORS encoded polyline to [[lat, lon], ...] list."""
    coords = []
    index = lat = lng = 0
    while index < len(encoded):
        for is_lng in (False, True):
            shift = result = 0
            while True:
                b = ord(encoded[index]) - 63
                index += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            value = ~(result >> 1) if result & 1 else result >> 1
            if is_lng:
                lng += value
            else:
                lat += value
        coords.append([lat / 1e5, lng / 1e5])
    return coords
