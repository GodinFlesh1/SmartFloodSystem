import pytest
from unittest.mock import AsyncMock, patch
from tests.conftest import STATION_STUB


def test_sync_stations_success(client):
    with patch("app.routers.sync.ea_service") as mock_ea, \
         patch("app.routers.sync.store_station", new_callable=AsyncMock) as mock_store:

        mock_ea.get_all_stations = AsyncMock(return_value={
            "success": True,
            "stations": [STATION_STUB, STATION_STUB],
        })
        mock_store.return_value = {"id": "uuid-1"}

        r = client.post("/api/sync/stations?limit=2")
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["fetched"] == 2
        assert body["stored"] == 2
        assert body["errors"] is None


def test_sync_stations_ea_error(client):
    with patch("app.routers.sync.ea_service") as mock_ea:
        mock_ea.get_all_stations = AsyncMock(return_value={
            "success": False,
            "error": "timeout",
        })
        r = client.post("/api/sync/stations")
        assert r.status_code == 200
        assert r.json()["success"] is False
        assert r.json()["error"] == "timeout"


def test_sync_stations_partial_store_error(client):
    with patch("app.routers.sync.ea_service") as mock_ea, \
         patch("app.routers.sync.store_station", new_callable=AsyncMock) as mock_store:

        mock_ea.get_all_stations = AsyncMock(return_value={
            "success": True,
            "stations": [STATION_STUB],
        })
        mock_store.side_effect = Exception("DB error")

        r = client.post("/api/sync/stations")
        body = r.json()
        assert body["success"] is True
        assert body["stored"] == 0
        assert body["errors"] is not None


def test_sync_readings(client):
    with patch("app.routers.sync.ea_service") as mock_ea:
        mock_ea.fetch_and_store_readings = AsyncMock(return_value={
            "success": True,
            "stored": 5,
        })
        r = client.post("/api/sync/readings/ABC123")
        assert r.status_code == 200
        assert r.json()["success"] is True
