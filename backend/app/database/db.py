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


# ── USERS ─────────────────────────────────────────────────────────────────────

async def upsert_user(user_data: dict) -> Optional[Dict]:
    """Insert or update a user row. Upserts on email."""
    try:
        result = supabase.table('users').upsert(user_data, on_conflict='email').execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"Error upserting user: {e}")
        return None


async def get_user_by_id(user_id: str) -> Optional[Dict]:
    try:
        result = supabase.table('users').select('*').eq('id', user_id).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"Error fetching user: {e}")
        return None


async def update_user_fcm_token(user_id: str, token: str) -> bool:
    """Store an FCM device token for a user."""
    try:
        supabase.table('users').update({'fcm_token': token}).eq('id', user_id).execute()
        return True
    except Exception as e:
        print(f"Error updating FCM token: {e}")
        return False


async def get_users_for_notifications() -> List[Dict]:
    """
    Return users that are eligible for push notifications:
      - notifications_enabled = true
      - fcm_token is not null
      - home_location is not null
    """
    try:
        result = (
            supabase.table('users')
            .select('id, fcm_token, home_location, last_alert_sent_at')
            .eq('notifications_enabled', True)
            .not_.is_('fcm_token', 'null')
            .not_.is_('home_location', 'null')
            .execute()
        )
        return result.data or []
    except Exception as e:
        print(f"Error fetching notification users: {e}")
        return []


async def mark_user_alerted(user_id: str) -> None:
    """Update last_alert_sent_at to now so we respect the 1-hour cooldown."""
    try:
        from datetime import datetime, timezone
        supabase.table('users').update(
            {'last_alert_sent_at': datetime.now(timezone.utc).isoformat()}
        ).eq('id', user_id).execute()
    except Exception as e:
        print(f"Error marking user alerted: {e}")


# ── DEVICE BINDING ────────────────────────────────────────────────────────────

async def get_device_id_for_user(firebase_uid: str) -> Optional[str]:
    try:
        result = (
            supabase.table('user_devices')
            .select('device_id')
            .eq('firebase_uid', firebase_uid)
            .execute()
        )
        return result.data[0]['device_id'] if result.data else None
    except Exception as e:
        print(f"Error fetching device_id: {e}")
        return None


async def register_device(firebase_uid: str, device_id: str) -> bool:
    try:
        supabase.table('user_devices').upsert(
            {'firebase_uid': firebase_uid, 'device_id': device_id},
            on_conflict='firebase_uid',
        ).execute()
        return True
    except Exception as e:
        print(f"Error registering device: {e}")
        return False


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
