from fastapi import APIRouter, Query
from app.dependencies import ea_service, predictor

router = APIRouter(prefix="/api", tags=["Prediction"])


@router.get("/predict/flood-risk")
async def predict_flood_risk(
    lat: float = Query(..., description="User latitude"),
    lon: float = Query(..., description="User longitude"),
    radius_km: float = Query(10, description="Search radius km"),
):
    """AI-powered flood prediction for the next 3 days using XGBoost."""
    stations_result = await ea_service.get_nearby_stations_live(lat, lon, radius_km)
    if not stations_result.get("success"):
        return {"success": False, "error": "Could not fetch nearby stations"}

    stations = stations_result.get("stations", [])
    return await predictor.predict(lat, lon, stations)
