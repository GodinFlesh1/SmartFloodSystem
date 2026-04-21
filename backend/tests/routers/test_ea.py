import pytest
from unittest.mock import AsyncMock, patch
from tests.conftest import STATION_STUB


@pytest.fixture(autouse=True)
def mock_ea(client):
    """Patch ea_service for every test in this module."""
    with patch("app.routers.ea.ea_service") as m:
        yield m


def test_live_nearby_stations_success(client, mock_ea):
    mock_ea.get_nearby_stations_live = AsyncMock(return_value={
        "success": True,
        "stations": [STATION_STUB],
        "count": 1,
    })
    r = client.get("/api/live/stations/nearby?lat=51.5&lon=-0.1&radius_km=10")
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["user_location"] == {"lat": 51.5, "lon": -0.1}
    assert len(body["stations"]) == 1


def test_live_nearby_stations_missing_lat(client, mock_ea):
    r = client.get("/api/live/stations/nearby?lon=-0.1")
    assert r.status_code == 422


def test_live_nearby_stations_ea_failure(client, mock_ea):
    mock_ea.get_nearby_stations_live = AsyncMock(return_value={
        "success": False,
        "error": "API down",
    })
    r = client.get("/api/live/stations/nearby?lat=51.5&lon=-0.1")
    assert r.status_code == 200
    assert r.json()["success"] is False


def test_get_ea_stations(client, mock_ea):
    mock_ea.get_all_stations = AsyncMock(return_value={
        "success": True,
        "total_stations": 2,
        "stations": [STATION_STUB, STATION_STUB],
    })
    r = client.get("/api/ea/stations?limit=2")
    assert r.status_code == 200
    assert r.json()["total_stations"] == 2


def test_get_ea_readings(client, mock_ea):
    mock_ea.get_station_readings = AsyncMock(return_value={
        "success": True,
        "station_id": "ABC123",
        "readings_count": 1,
        "readings": [{"value": 1.2, "dateTime": "2024-06-01T12:00:00Z"}],
    })
    r = client.get("/api/ea/stations/ABC123/readings?limit=1")
    assert r.status_code == 200
    assert r.json()["success"] is True


def test_get_station_latest(client, mock_ea):
    mock_ea.get_station_latest_all_measures = AsyncMock(return_value={
        "success": True,
        "station_id": "ABC123",
        "measures": [],
    })
    r = client.get("/api/ea/stations/ABC123/latest")
    assert r.status_code == 200
    assert r.json()["success"] is True
