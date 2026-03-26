from supabase import create_client, Client
from dotenv import load_dotenv
import os
from typing import Dict, List, Optional
from math import radians, cos, sin, asin, sqrt

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def get_supabase() -> Client:
    return supabase


# ── STATIONS ──────────────────────────────────────────────────────────────────

async def store_station(station_data: Dict) -> Optional[Dict]:
    try:
        data = {
            'ea_station_id': station_data.get('stationReference'),
            'station_name': station_data.get('label'),
            'latitude': station_data.get('lat'),
            'longitude': station_data.get('long'),
            'town': station_data.get('town'),
            'river_name': station_data.get('riverName'),
        }
        result = supabase.table('stations').upsert(data, on_conflict='ea_station_id').execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"Error storing station: {e}")
        return None


async def get_station_by_ea_id(ea_station_id: str) -> Optional[Dict]:
    try:
        result = supabase.table('stations').select('*').eq('ea_station_id', ea_station_id).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"Error fetching station: {e}")
        return None


async def get_all_stations_from_db() -> List[Dict]:
    try:
        result = supabase.table('stations').select('*').execute()
        return result.data or []
    except Exception as e:
        print(f"Error fetching stations: {e}")
        return []


# ── READINGS ──────────────────────────────────────────────────────────────────

async def store_reading(station_id: str, ea_station_id: str, reading_data: Dict) -> Optional[Dict]:
    try:
        data = {
            'station_id': station_id,
            'ea_station_id': ea_station_id,
            'water_level': reading_data.get('value'),
            'timestamp': reading_data.get('dateTime'),
        }
        result = supabase.table('readings').insert(data).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"Error storing reading: {e}")
        return None


async def get_latest_reading_for_station(station_id: str) -> Optional[Dict]:
    try:
        result = supabase.table('readings') \
            .select('*') \
            .eq('station_id', station_id) \
            .order('timestamp', desc=True) \
            .limit(1).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"Error fetching latest reading: {e}")
        return None


async def get_readings_history(station_id: str, limit: int = 48) -> List[Dict]:
    """Return up to `limit` most-recent readings for a station, oldest-first."""
    try:
        result = supabase.table('readings') \
            .select('water_level,timestamp') \
            .eq('station_id', station_id) \
            .order('timestamp', desc=True) \
            .limit(limit).execute()
        data = result.data or []
        data.reverse()   # oldest first for charting
        return data
    except Exception as e:
        print(f"Error fetching readings history: {e}")
        return []


# ── GEO ───────────────────────────────────────────────────────────────────────

def _haversine(lat1, lon1, lat2, lon2) -> float:
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    return 6371 * 2 * asin(sqrt(a))


async def find_nearby_stations(lat: float, lon: float, radius_km: float = 10) -> List[Dict]:
    try:
        result = supabase.table('stations').select('*').execute()
        if not result.data:
            return []
        nearby = []
        for s in result.data:
            if s.get('latitude') and s.get('longitude'):
                d = _haversine(lat, lon, s['latitude'], s['longitude'])
                if d <= radius_km:
                    s['distance_km'] = round(d, 2)
                    nearby.append(s)
        nearby.sort(key=lambda x: x['distance_km'])
        return nearby
    except Exception as e:
        print(f"Error finding nearby stations: {e}")
        return []
