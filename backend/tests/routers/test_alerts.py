from unittest.mock import AsyncMock, patch
from tests.conftest import STATION_STUB


def test_get_active_alerts_none(client):
    with patch("app.routers.alerts.get_all_stations_from_db", new_callable=AsyncMock) as mock_db, \
         patch("app.routers.alerts.risk_calc") as mock_risk:

        mock_db.return_value = [dict(STATION_STUB, id="uuid-1")]
        mock_risk.assess_risk = AsyncMock(return_value={
            "station_id": "ABC123",
            "risk_level": "LOW",
            "risk_score": 0,
        })

        r = client.get("/api/alerts")
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["alert_count"] == 0
        assert body["alerts"] == []


def test_get_active_alerts_with_high_risk(client):
    with patch("app.routers.alerts.get_all_stations_from_db", new_callable=AsyncMock) as mock_db, \
         patch("app.routers.alerts.risk_calc") as mock_risk:

        mock_db.return_value = [
            dict(STATION_STUB, id="uuid-1"),
            dict(STATION_STUB, id="uuid-2", station_name="Flood Station"),
        ]
        mock_risk.assess_risk = AsyncMock(side_effect=[
            {"station_id": "ABC123", "risk_level": "LOW",      "risk_score": 0},
            {"station_id": "XYZ999", "risk_level": "CRITICAL", "risk_score": 4},
        ])

        r = client.get("/api/alerts")
        body = r.json()
        assert body["alert_count"] == 1
        assert body["alerts"][0]["risk_level"] == "CRITICAL"
        assert body["alerts"][0]["station_name"] == "Flood Station"


def test_get_active_alerts_empty_db(client):
    with patch("app.routers.alerts.get_all_stations_from_db", new_callable=AsyncMock) as mock_db:
        mock_db.return_value = []
        r = client.get("/api/alerts")
        assert r.json()["alert_count"] == 0
