from unittest.mock import AsyncMock, patch
from tests.conftest import STATION_STUB


def test_get_flood_map_success(client):
    with patch("app.routers.flood_map.ea_service") as mock_ea:
        stations = [
            dict(STATION_STUB, risk_level="NORMAL"),
            dict(STATION_STUB, station_name="S2", ea_station_id="XYZ", risk_level="HIGH"),
        ]
        mock_ea.get_nearby_stations_live = AsyncMock(return_value={
            "success": True,
            "stations": stations,
        })

        r = client.get("/api/flood-map?lat=51.5&lon=-0.1&radius_km=20")
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["point_count"] == 2
        assert body["center"] == {"lat": 51.5, "lon": -0.1}


def test_get_flood_map_filters_missing_coords(client):
    with patch("app.routers.flood_map.ea_service") as mock_ea:
        mock_ea.get_nearby_stations_live = AsyncMock(return_value={
            "success": True,
            "stations": [
                dict(STATION_STUB, latitude=None, longitude=None),
                STATION_STUB,
            ],
        })
        r = client.get("/api/flood-map?lat=51.5&lon=-0.1")
        body = r.json()
        assert body["point_count"] == 1


def test_get_flood_map_ea_failure(client):
    with patch("app.routers.flood_map.ea_service") as mock_ea:
        mock_ea.get_nearby_stations_live = AsyncMock(return_value={
            "success": False,
            "error": "timeout",
        })
        r = client.get("/api/flood-map?lat=51.5&lon=-0.1")
        assert r.json()["success"] is False


def test_get_flood_map_requires_lat_lon(client):
    r = client.get("/api/flood-map")
    assert r.status_code == 422
