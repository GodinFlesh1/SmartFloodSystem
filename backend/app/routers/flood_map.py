from fastapi import APIRouter, Query
from app.dependencies import ea_service

router = APIRouter(prefix="/api", tags=["Flood Map"])


@router.get("/flood-map")
async def get_flood_map(
    lat: float = Query(...),
    lon: float = Query(...),
    radius_km: float = Query(25),
):
    """Returns station positions with risk level for map overlay. Uses live EA data."""
    result = await ea_service.get_nearby_stations_live(lat, lon, radius_km)
    if not result.get("success"):
        return result

    map_points = [
        {
            "ea_station_id": s["ea_station_id"],
            "station_name": s["station_name"],
            "latitude": s["latitude"],
            "longitude": s["longitude"],
            "town": s.get("town"),
            "river_name": s.get("river_name"),
            "water_level": s.get("water_level"),
            "risk_level": s.get("risk_level", "UNKNOWN"),
            "distance_km": s.get("distance_km"),
        }
        for s in result["stations"]
        if s.get("latitude") and s.get("longitude")
    ]

    return {
        "success": True,
        "center": {"lat": lat, "lon": lon},
        "radius_km": radius_km,
        "point_count": len(map_points),
        "points": map_points,
    }
