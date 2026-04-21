"""
Safe route and shelter service.
- Finds nearest safe shelters using OpenStreetMap Overpass API (free, no key)
- Calculates driving/walking route using OpenRouteService API
"""

import asyncio
import os
import httpx
from typing import Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()

ORS_BASE = "https://api.openrouteservice.org"

OVERPASS_MIRRORS = [
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.ru/api/interpreter",
]
OVERPASS_HEADERS = {
    "User-Agent": "EcoFlood/1.0 (academic flood-risk app; contact ishitajana20050@gmail.com)",
    "Accept":     "application/json",
}

SHELTER_QUERY = """
[out:json][timeout:30];
(
  node["amenity"="community_centre"](around:{radius},{lat},{lon});
  node["amenity"="school"](around:{radius},{lat},{lon});
  node["amenity"="hospital"](around:{radius},{lat},{lon});
  node["amenity"="place_of_worship"](around:{radius},{lat},{lon});
  node["building"="civic"](around:{radius},{lat},{lon});
  node["emergency"="assembly_point"](around:{radius},{lat},{lon});
  node["amenity"="shelter"](around:{radius},{lat},{lon});
  node["amenity"="police"](around:{radius},{lat},{lon});
  node["amenity"="fire_station"](around:{radius},{lat},{lon});
);
out body;
"""


class RouteService:

    async def _fetch_overpass(self, lat: float, lon: float, radius_m: int) -> List[Dict]:
        """Query Overpass mirrors in order; tries GET then POST per mirror."""
        query = SHELTER_QUERY.format(lat=lat, lon=lon, radius=radius_m)
        elements: List[Dict] = []
        async with httpx.AsyncClient(timeout=30, headers=OVERPASS_HEADERS) as client:
            for mirror in OVERPASS_MIRRORS:
                try:
                    resp = await client.get(mirror, params={"data": query})
                    if resp.status_code == 200:
                        elements = resp.json().get("elements", [])
                        break
                    resp = await client.post(mirror, data={"data": query})
                    if resp.status_code == 200:
                        elements = resp.json().get("elements", [])
                        break
                except Exception:
                    continue
        if not elements:
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

            dist    = _haversine(lat, lon, place_lat, place_lon)
            amenity = tags.get("amenity", tags.get("building", "shelter"))

            places.append({
                "name":        name,
                "type":        amenity,
                "latitude":    place_lat,
                "longitude":   place_lon,
                "distance_m":  round(dist * 1000),
                "distance_km": round(dist, 2),
                "address":     tags.get("addr:street", ""),
            })

        places.sort(key=lambda x: x["distance_m"])
        return places

    async def get_safe_places(
        self, lat: float, lon: float, radius_m: int = 5000
    ) -> List[Dict]:
        """
        Search for safe shelters with automatic radius expansion and retry.
        Tries [radius_m, 2x, 4x] until shelters are found or all attempts fail.
        """
        search_radii = [radius_m, radius_m * 2, min(radius_m * 4, 20000)]

        for attempt_radius in search_radii:
            # Two attempts per radius level
            for _ in range(2):
                places = await self._fetch_overpass(lat, lon, attempt_radius)
                if places:
                    return places[:10]
                await asyncio.sleep(1)

        return []

    async def get_route(
        self,
        from_lat: float, from_lon: float,
        to_lat: float,   to_lon: float,
        profile: str = "driving-car",
    ) -> Dict:
        ors_key = os.getenv("ORS_API_KEY", "")
        if not ors_key:
            return {"success": False, "error": "Routing service not configured"}

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

        async with httpx.AsyncClient(timeout=25) as client:
            try:
                resp = await client.post(url, json=body, headers=headers)
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPStatusError as e:
                return {"success": False, "error": f"Routing API error {e.response.status_code}"}
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

            coords = _decode_polyline(route["geometry"])

            return {
                "success":      True,
                "distance_m":   round(summary["distance"]),
                "duration_s":   round(summary["duration"]),
                "distance_km":  round(summary["distance"] / 1000, 2),
                "duration_min": round(summary["duration"] / 60),
                "coordinates":  coords,
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
                "success":      False,
                "error":        "No safe shelters found in your area. Try moving to a different location.",
                "all_shelters": [],
            }

        nearest = places[0]
        route   = await self.get_route(
            from_lat=lat,               from_lon=lon,
            to_lat=nearest["latitude"], to_lon=nearest["longitude"],
            profile=profile,
        )

        if not route.get("success"):
            # Return shelters even when routing fails so the user can still see options
            return {
                "success":       True,
                "shelter":       nearest,
                "all_shelters":  places,
                "route": {
                    "coordinates":  [],
                    "steps":        [],
                    "distance_m":   nearest["distance_m"],
                    "distance_km":  nearest["distance_km"],
                    "duration_min": 0,
                    "profile":      profile,
                },
                "route_warning": route.get("error", "Turn-by-turn routing unavailable"),
            }

        return {
            "success":      True,
            "shelter":      nearest,
            "all_shelters": places,
            "route":        route,
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
