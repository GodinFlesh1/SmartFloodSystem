from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from app.services.ea_api import EnvironmentAgencyService
from app.services.risk_calculator import RiskCalculator
from app.services.flood_predictor import FloodPredictor
from app.services.route_service import RouteService
from app.database.db import (
    store_station,
    get_all_stations_from_db,
    find_nearby_stations,
    get_latest_reading_for_station,
    get_readings_history,
)

app = FastAPI(
    title="EcoFlood API",
    description="Real-time flood monitoring and early-warning system",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

ea_service     = EnvironmentAgencyService()
risk_calc      = RiskCalculator()
predictor      = FloodPredictor()
route_service  = RouteService()

# ── HEALTH ────────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {"message": "EcoFlood API is running", "status": "healthy", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    return {"status": "ok"}

# ── LIVE EA API (no DB required) ──────────────────────────────────────────────

@app.get("/api/live/stations/nearby")
async def live_nearby_stations(
    lat: float = Query(..., description="Latitude", example=51.5074),
    lon: float = Query(..., description="Longitude", example=-0.1278),
    radius_km: float = Query(10, description="Search radius km"),
):
    """
    Query the Environment Agency API directly for nearby stations with
    current water levels and snapshot risk assessment. No DB needed.
    """
    result = await ea_service.get_nearby_stations_live(lat, lon, radius_km)
    if result.get("success"):
        result["user_location"] = {"lat": lat, "lon": lon}
    return result


@app.get("/api/ea/stations")
async def get_ea_stations(limit: int = Query(50)):
    return await ea_service.get_all_stations(limit)


@app.get("/api/ea/stations/{station_id}/readings")
async def get_ea_readings(station_id: str, limit: int = Query(24)):
    return await ea_service.get_station_readings(station_id, limit)


@app.get("/api/ea/stations/{station_id}/latest")
async def get_station_latest(station_id: str):
    """Latest reading for every measure at a station (level, flow, groundwater, etc.)"""
    return await ea_service.get_station_latest_all_measures(station_id)

# ── DB SYNC ───────────────────────────────────────────────────────────────────

@app.post("/api/sync/stations")
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


@app.post("/api/sync/readings/{station_id}")
async def sync_readings(station_id: str):
    return await ea_service.fetch_and_store_readings(station_id)

# ── DB QUERY ──────────────────────────────────────────────────────────────────

@app.get("/api/database/stations")
async def get_db_stations():
    stations = await get_all_stations_from_db()
    return {"success": True, "count": len(stations), "stations": stations}


@app.get("/api/stations/nearby")
async def get_nearby_stations(
    lat: float = Query(..., example=51.5074),
    lon: float = Query(..., example=-0.1278),
    radius_km: float = Query(10),
):
    """Nearby stations from DB with latest readings."""
    stations = await find_nearby_stations(lat, lon, radius_km)
    for s in stations:
        s["latest_reading"] = await get_latest_reading_for_station(s["id"])
    return {
        "success": True,
        "user_location": {"lat": lat, "lon": lon},
        "radius_km": radius_km,
        "stations_found": len(stations),
        "stations": stations,
    }

# ── RISK ASSESSMENT ───────────────────────────────────────────────────────────

@app.get("/api/stations/{station_id}/risk")
async def get_station_risk(station_id: str):
    """Velocity-based risk assessment for a DB station."""
    return await risk_calc.assess_risk(station_id)


@app.get("/api/stations/{station_id}/readings/history")
async def get_station_readings_history(
    station_id: str,
    limit: int = Query(48, description="Number of readings (max 96)"),
):
    """Historical readings for charting."""
    limit = min(limit, 96)
    readings = await get_readings_history(station_id, limit)
    return {"success": True, "station_id": station_id, "count": len(readings), "readings": readings}

# ── ALERTS ────────────────────────────────────────────────────────────────────

@app.get("/api/alerts")
async def get_active_alerts():
    """
    Assess risk for all DB stations and return those with HIGH or CRITICAL level.
    """
    stations = await get_all_stations_from_db()
    alerts = []
    for s in stations:
        risk = await risk_calc.assess_risk(s["id"])
        if risk["risk_level"] in ("HIGH", "CRITICAL"):
            alerts.append({
                **risk,
                "station_name": s["station_name"],
                "town": s.get("town"),
                "river_name": s.get("river_name"),
                "latitude": s.get("latitude"),
                "longitude": s.get("longitude"),
            })
    return {
        "success": True,
        "alert_count": len(alerts),
        "alerts": alerts,
    }

# ── FLOOD MAP DATA ────────────────────────────────────────────────────────────

@app.get("/api/flood-map")
async def get_flood_map(
    lat: float = Query(...),
    lon: float = Query(...),
    radius_km: float = Query(25),
):
    """
    Returns station positions with risk level for map overlay.
    Uses live EA data so no DB sync is required.
    """
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

# ── AI FLOOD PREDICTION ───────────────────────────────────────────────────────

@app.get("/api/predict/flood-risk")
async def predict_flood_risk(
    lat: float = Query(..., description="User latitude"),
    lon: float = Query(..., description="User longitude"),
    radius_km: float = Query(10, description="Search radius km"),
):
    """
    AI-powered flood prediction for the next 3 days.
    Fetches nearby stations + live weather, runs the XGBoost model,
    and returns risk level with probability and reason.
    """
    # Get nearby stations with current water levels
    stations_result = await ea_service.get_nearby_stations_live(lat, lon, radius_km)
    if not stations_result.get("success"):
        return {"success": False, "error": "Could not fetch nearby stations"}

    stations = stations_result.get("stations", [])
    return await predictor.predict(lat, lon, stations)

# ── SAFE ROUTES ───────────────────────────────────────────────────────────────

@app.get("/api/safe-places")
async def get_safe_places(
    lat: float = Query(...),
    lon: float = Query(...),
    radius_m: int = Query(5000, description="Search radius in metres"),
):
    """Nearest safe shelter places from OpenStreetMap."""
    places = await route_service.get_safe_places(lat, lon, radius_m)
    return {"success": True, "count": len(places), "places": places}


@app.get("/api/safe-route")
async def get_safe_route(
    lat: float = Query(..., description="User latitude"),
    lon: float = Query(..., description="User longitude"),
    radius_m: int = Query(5000, description="Shelter search radius in metres"),
    profile: str = Query("driving-car", description="driving-car | foot-walking"),
):
    """
    Finds the nearest safe shelter and returns the route to it.
    Used by Flutter when flood risk is HIGH or SEVERE.
    """
    return await route_service.get_safe_route_to_shelter(
        lat=lat, lon=lon, radius_m=radius_m, profile=profile
    )
