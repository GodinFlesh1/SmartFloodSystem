import os
import pytest

# Must be set before any app module is imported so db.py can call create_client()
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-anon-key")
os.environ.setdefault("ORS_API_KEY", "test-ors-key")

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


# ── Shared station/reading stubs ──────────────────────────────────────────────

STATION_STUB = {
    "ea_station_id": "ABC123",
    "station_name": "Test Station",
    "latitude": 51.5,
    "longitude": -0.1,
    "town": "London",
    "river_name": "Thames",
    "water_level": 1.2,
    "flow": None,
    "rainfall": None,
    "groundwater": None,
    "tidal": None,
    "distance_km": 3.5,
    "risk_level": "NORMAL",
}

READING_STUB = {
    "id": "r1",
    "station_id": "uuid-station-1",
    "ea_station_id": "ABC123",
    "water_level": 1.2,
    "timestamp": "2024-06-01T12:00:00",
}

RISK_STUB = {
    "station_id": "ABC123",
    "risk_level": "LOW",
    "risk_score": 0,
    "velocity_1hr": 0.01,
    "velocity_3hr": 0.01,
    "velocity_6hr": 0.01,
    "assessed_at": "2024-06-01T12:00:00",
}
