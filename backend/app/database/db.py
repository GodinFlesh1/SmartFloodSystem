from supabase import create_client, Client
from dotenv import load_dotenv
import os
from typing import Dict, List, Optional

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_supabase():
    """Get Supabase client"""
    return supabase

# ========== STATION OPERATIONS ==========

async def store_station(station_data: Dict) -> Optional[Dict]:
    """Store or update a station in the database"""
    try:
        data = {
            'ea_station_id': station_data.get('stationReference'),
            'station_name': station_data.get('label'),
            'latitude': station_data.get('lat'),
            'longitude': station_data.get('long'),
            'town': station_data.get('town'),
            'river_name': station_data.get('riverName')
        }
        
        result = supabase.table('stations').upsert(
            data,
            on_conflict='ea_station_id'
        ).execute()
        
        return result.data[0] if result.data else None
        
    except Exception as e:
        print(f"Error storing station: {e}")
        return None

async def get_station_by_ea_id(ea_station_id: str) -> Optional[Dict]:
    """Get station from database by EA station ID"""
    try:
        result = supabase.table('stations')\
            .select('*')\
            .eq('ea_station_id', ea_station_id)\
            .execute()
        
        return result.data[0] if result.data else None
        
    except Exception as e:
        print(f"Error fetching station: {e}")
        return None

async def get_all_stations_from_db() -> List[Dict]:
    """Get all stations from database"""
    try:
        result = supabase.table('stations').select('*').execute()
        return result.data if result.data else []
        
    except Exception as e:
        print(f"Error fetching stations: {e}")
        return []

# ========== READING OPERATIONS ==========

async def store_reading(station_id: str, ea_station_id: str, reading_data: Dict) -> Optional[Dict]:
    """Store a water level reading"""
    try:
        data = {
            'station_id': station_id,
            'ea_station_id': ea_station_id,
            'water_level': reading_data.get('value'),
            'timestamp': reading_data.get('dateTime')
        }
        
        result = supabase.table('readings').insert(data).execute()
        return result.data[0] if result.data else None
        
    except Exception as e:
        print(f"Error storing reading: {e}")
        return None

async def get_latest_reading_for_station(station_id: str) -> Optional[Dict]:
    """Get the most recent reading for a station"""
    try:
        result = supabase.table('readings')\
            .select('*')\
            .eq('station_id', station_id)\
            .order('timestamp', desc=True)\
            .limit(1)\
            .execute()
        
        return result.data[0] if result.data else None
        
    except Exception as e:
        print(f"Error fetching latest reading: {e}")
        return None

# ========== GEO-SPATIAL OPERATIONS ==========

async def find_nearby_stations(lat: float, lon: float, radius_km: float = 10) -> List[Dict]:
    """Find stations within radius_km of given coordinates"""
    from math import radians, cos, sin, asin, sqrt
    
    def calculate_distance(lat1, lon1, lat2, lon2):
        """Calculate distance between two points in kilometers"""
        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        return 6371 * c
    
    try:
        result = supabase.table('stations').select('*').execute()
        
        if not result.data:
            return []
        
        nearby = []
        for station in result.data:
            distance = calculate_distance(
                lat, lon,
                station['latitude'], station['longitude']
            )
            
            if distance <= radius_km:
                station['distance_km'] = round(distance, 2)
                nearby.append(station)
        
        nearby.sort(key=lambda x: x['distance_km'])
        return nearby
        
    except Exception as e:
        print(f"Error finding nearby stations: {e}")
        return []