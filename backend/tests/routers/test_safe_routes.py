from unittest.mock import AsyncMock, patch

PLACE_STUB = {
    "name": "Community Hall",
    "type": "community_centre",
    "latitude": 51.51,
    "longitude": -0.09,
    "distance_m": 800,
    "distance_km": 0.8,
    "address": "High Street",
}

ROUTE_STUB = {
    "success": True,
    "shelter": PLACE_STUB,
    "all_shelters": [PLACE_STUB],
    "route": {
        "success": True,
        "distance_m": 800,
        "distance_km": 0.8,
        "duration_s": 120,
        "duration_min": 2,
        "coordinates": [[51.5, -0.1], [51.51, -0.09]],
        "steps": [],
        "profile": "driving-car",
    },
    "error": None,
}


def test_get_safe_places_success(client):
    with patch("app.routers.safe_routes.route_service") as mock_rs:
        mock_rs.get_safe_places = AsyncMock(return_value=[PLACE_STUB])
        r = client.get("/api/safe-places?lat=51.5&lon=-0.1&radius_m=1000")
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["count"] == 1
        assert body["places"][0]["name"] == "Community Hall"


def test_get_safe_places_empty(client):
    with patch("app.routers.safe_routes.route_service") as mock_rs:
        mock_rs.get_safe_places = AsyncMock(return_value=[])
        r = client.get("/api/safe-places?lat=51.5&lon=-0.1")
        assert r.json()["count"] == 0


def test_get_safe_places_requires_lat_lon(client):
    r = client.get("/api/safe-places")
    assert r.status_code == 422


def test_get_safe_route_success(client):
    with patch("app.routers.safe_routes.route_service") as mock_rs:
        mock_rs.get_safe_route_to_shelter = AsyncMock(return_value=ROUTE_STUB)
        r = client.get("/api/safe-route?lat=51.5&lon=-0.1&profile=foot-walking")
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["shelter"]["name"] == "Community Hall"


def test_get_safe_route_no_shelters(client):
    with patch("app.routers.safe_routes.route_service") as mock_rs:
        mock_rs.get_safe_route_to_shelter = AsyncMock(return_value={
            "success": False,
            "error": "No safe shelters found within radius.",
            "all_shelters": [],
        })
        r = client.get("/api/safe-route?lat=51.5&lon=-0.1")
        assert r.json()["success"] is False
