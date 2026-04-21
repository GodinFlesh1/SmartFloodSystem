from unittest.mock import AsyncMock, patch
from tests.conftest import STATION_STUB


def test_predict_flood_risk_success(client):
    with patch("app.routers.prediction.ea_service") as mock_ea, \
         patch("app.routers.prediction.predictor") as mock_pred:

        mock_ea.get_nearby_stations_live = AsyncMock(return_value={
            "success": True,
            "stations": [STATION_STUB],
        })
        mock_pred.predict = AsyncMock(return_value={
            "success": True,
            "risk_level": "NORMAL",
            "probability": 0.05,
            "confidence": "high",
            "reason": "Normal conditions.",
            "top_station": "Test Station",
            "station_predictions": [],
        })

        r = client.get("/api/predict/flood-risk?lat=51.5&lon=-0.1&radius_km=10")
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["risk_level"] == "NORMAL"


def test_predict_flood_risk_ea_failure(client):
    with patch("app.routers.prediction.ea_service") as mock_ea:
        mock_ea.get_nearby_stations_live = AsyncMock(return_value={
            "success": False,
            "error": "timeout",
        })
        r = client.get("/api/predict/flood-risk?lat=51.5&lon=-0.1")
        body = r.json()
        assert body["success"] is False
        assert "stations" in body["error"]


def test_predict_flood_risk_requires_lat_lon(client):
    r = client.get("/api/predict/flood-risk")
    assert r.status_code == 422
