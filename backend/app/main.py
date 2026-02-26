from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from app.services.ea_api import EnvironmentAgencyService
from app.database.db import (
    store_station, 
    get_all_stations_from_db,
    find_nearby_stations,
    get_latest_reading_for_station
)

app = FastAPI(
    title="EcoFlood API",
    description="Real-time flood monitoring system",
    version="1.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
ea_service = EnvironmentAgencyService()

# ========== BASIC ENDPOINTS ==========

@app.get("/")
async def root():
    return {
        "message": "EcoFlood API is running",
        "status": "healthy",
        "version": "1.0.0"
    }

@app.get("/health")
async def health_check():
    return {"status": "ok"}

# ========== ENVIRONMENT AGENCY API ENDPOINTS ==========

@app.get("/api/ea/stations")
async def get_ea_stations(limit: int = Query(50, description="Number of stations")):
    """Get stations directly from UK Environment Agency API"""
    result = await ea_service.get_all_stations(limit)
    return result

@app.get("/api/ea/stations/{station_id}/readings")
async def get_ea_readings(
    station_id: str, 
    limit: int = Query(10, description="Number of readings")
):
    """Get readings directly from UK Environment Agency API"""
    result = await ea_service.get_station_readings(station_id, limit)
    return result

# ========== DATABASE SYNC ENDPOINTS ==========

@app.post("/api/sync/stations")
async def sync_stations_to_database(limit: int = Query(100, description="Number of stations to sync")):
    """Fetch stations from EA API and store in our database"""
    result = await ea_service.get_all_stations(limit)
    
    if not result.get('success'):
        return {"success": False, "error": result.get('error')}
    
    stations = result.get('stations', [])
    stored_count = 0
    errors = []
    
    for station in stations:
        try:
            stored = await store_station(station)
            if stored:
                stored_count += 1
        except Exception as e:
            errors.append(f"Error with {station.get('stationReference')}: {str(e)}")
    
    return {
        "success": True,
        "fetched": len(stations),
        "stored": stored_count,
        "errors": errors if errors else None
    }

@app.post("/api/sync/readings/{station_id}")
async def sync_station_readings(station_id: str):
    """Fetch and store readings for a specific station"""
    result = await ea_service.fetch_and_store_readings(station_id)
    return result

# ========== DATABASE QUERY ENDPOINTS ==========

@app.get("/api/database/stations")
async def get_database_stations():
    """Get all stations from our database"""
    stations = await get_all_stations_from_db()
    return {
        "success": True,
        "count": len(stations),
        "stations": stations
    }

#currently unused - will be used for Flutter app
@app.get("/api/stations/nearby")
async def get_nearby_stations_endpoint(
    lat: float = Query(..., description="Your latitude", example=51.5074),
    lon: float = Query(..., description="Your longitude", example=-0.1278),
    radius_km: float = Query(10, description="Search radius in km", example=10)
):
    """Find flood monitoring stations near your location with latest water levels"""
    stations = await find_nearby_stations(lat, lon, radius_km)
    
    # Add latest reading for each station
    for station in stations:
        latest = await get_latest_reading_for_station(station['id'])
        station['latest_reading'] = latest
    
    return {
        "success": True,
        "user_location": {"lat": lat, "lon": lon},
        "radius_km": radius_km,
        "stations_found": len(stations),
        "stations": stations
    }

