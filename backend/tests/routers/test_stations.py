import pytest
from unittest.mock import AsyncMock, patch
from tests.conftest import STATION_STUB, READING_STUB, RISK_STUB


def test_get_db_stations(client):
    with patch("app.routers.stations.get_all_stations_from_db", new_callable=AsyncMock) as mock_db:
        mock_db.return_value = [STATION_STUB]
        r = client.get("/api/database/stations")
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["count"] == 1
        assert body["stations"][0]["station_name"] == "Test Station"


def test_get_db_stations_empty(client):
    with patch("app.routers.stations.get_all_stations_from_db", new_callable=AsyncMock) as mock_db:
        mock_db.return_value = []
        r = client.get("/api/database/stations")
        assert r.json()["count"] == 0


def test_get_nearby_stations(client):
    with patch("app.routers.stations.find_nearby_stations", new_callable=AsyncMock) as mock_find, \
         patch("app.routers.stations.get_latest_reading_for_station", new_callable=AsyncMock) as mock_reading:

        s = dict(STATION_STUB, id="uuid-1")
        mock_find.return_value = [s]
        mock_reading.return_value = READING_STUB

        r = client.get("/api/stations/nearby?lat=51.5&lon=-0.1&radius_km=10")
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["stations_found"] == 1
        assert body["stations"][0]["latest_reading"]["water_level"] == 1.2


def test_get_nearby_stations_requires_lat_lon(client):
    r = client.get("/api/stations/nearby?lat=51.5")
    assert r.status_code == 422


def test_get_station_risk(client):
    with patch("app.routers.stations.risk_calc") as mock_risk:
        mock_risk.assess_risk = AsyncMock(return_value=RISK_STUB)
        r = client.get("/api/stations/ABC123/risk")
        assert r.status_code == 200
        assert r.json()["risk_level"] == "LOW"


def test_get_readings_history(client):
    with patch("app.routers.stations.get_readings_history", new_callable=AsyncMock) as mock_hist:
        mock_hist.return_value = [READING_STUB] * 10
        r = client.get("/api/stations/ABC123/readings/history?limit=10")
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["count"] == 10


def test_get_readings_history_limit_capped(client):
    with patch("app.routers.stations.get_readings_history", new_callable=AsyncMock) as mock_hist:
        mock_hist.return_value = [READING_STUB] * 96
        r = client.get("/api/stations/ABC123/readings/history?limit=200")
        assert r.status_code == 200
        # Verify limit was capped: get_readings_history called with limit=96
        mock_hist.assert_called_once_with("ABC123", 96)
