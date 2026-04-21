from fastapi import APIRouter, Query
from app.dependencies import ea_service

router = APIRouter(prefix="/api", tags=["Environment Agency"])


@router.get("/live/stations/nearby")
async def live_nearby_stations(
    lat: float = Query(..., description="Latitude", example=51.5074),
    lon: float = Query(..., description="Longitude", example=-0.1278),
    radius_km: float = Query(10, description="Search radius km"),
):
    """Query the EA API directly for nearby stations with current water levels. No DB needed."""
    result = await ea_service.get_nearby_stations_live(lat, lon, radius_km)
    if result.get("success"):
        result["user_location"] = {"lat": lat, "lon": lon}
    return result


@router.get("/ea/stations")
async def get_ea_stations(limit: int = Query(50)):
    return await ea_service.get_all_stations(limit)


@router.get("/ea/stations/{station_id}/readings")
async def get_ea_readings(station_id: str, limit: int = Query(24)):
    return await ea_service.get_station_readings(station_id, limit)


@router.get("/ea/stations/{station_id}/latest")
async def get_station_latest(station_id: str):
    """Latest reading for every measure at a station (level, flow, groundwater, etc.)"""
    return await ea_service.get_station_latest_all_measures(station_id)
