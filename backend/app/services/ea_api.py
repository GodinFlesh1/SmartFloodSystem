import httpx
from typing import List, Dict, Optional

class EnvironmentAgencyService:
    BASE_URL = "https://environment.data.gov.uk/flood-monitoring"
    
    async def get_all_stations(self, limit: int = 50) -> Dict:
        """Fetch flood monitoring stations from UK Environment Agency"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    f"{self.BASE_URL}/id/stations",
                    params={"_limit": limit}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    items = data.get('items', [])
                    
                    return {
                        "success": True,
                        "total_stations": len(items),
                        "stations": items
                    }
                else:
                    return {
                        "success": False,
                        "error": f"API returned status code {response.status_code}"
                    }
                    
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e)
                }
    
    async def get_station_readings(self, station_id: str, limit: int = 10) -> Dict:
        """Get latest water level readings for a station"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    f"{self.BASE_URL}/id/stations/{station_id}/readings",
                    params={
                        "latest": limit,
                        "_sorted": "dateTime"
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    items = data.get('items', [])
                    
                    return {
                        "success": True,
                        "station_id": station_id,
                        "readings_count": len(items),
                        "readings": items
                    }
                else:
                    return {
                        "success": False,
                        "error": f"API returned status code {response.status_code}"
                    }
                    
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e)
                }
    
    async def fetch_and_store_readings(self, ea_station_id: str) -> Dict:
        """Fetch readings from EA API and store in database"""
        from app.database.db import get_station_by_ea_id, store_reading
        
        station = await get_station_by_ea_id(ea_station_id)
        
        if not station:
            return {
                "success": False,
                "error": "Station not found in database. Please sync stations first."
            }
        
        readings_result = await self.get_station_readings(ea_station_id, limit=10)
        
        if not readings_result.get('success'):
            return readings_result
        
        readings = readings_result.get('readings', [])
        stored_count = 0
        
        for reading in readings:
            try:
                stored = await store_reading(
                    station_id=station['id'],
                    ea_station_id=ea_station_id,
                    reading_data=reading
                )
                if stored:
                    stored_count += 1
            except Exception as e:
                print(f"Error storing reading: {e}")
        
        return {
            "success": True,
            "station_id": ea_station_id,
            "station_name": station['station_name'],
            "fetched": len(readings),
            "stored": stored_count
        }