from fastapi import APIRouter, Query
from app.dependencies import ea_service
from app.database.db import store_station

router = APIRouter(prefix="/api/sync", tags=["Sync"])


@router.post("/stations")
async def sync_stations(limit: int = Query(100)):
    result = await ea_service.get_all_stations(limit)
    if not result.get("success"):
        return {"success": False, "error": result.get("error")}

    stations = result.get("stations", [])
    stored_count = 0
    errors = []
    for s in stations:
        try:
            stored = await store_station(s)
            if stored:
                stored_count += 1
        except Exception as e:
            errors.append(str(e))

    return {
        "success": True,
        "fetched": len(stations),
        "stored": stored_count,
        "errors": errors or None,
    }


@router.post("/readings/{station_id}")
async def sync_readings(station_id: str):
    return await ea_service.fetch_and_store_readings(station_id)
