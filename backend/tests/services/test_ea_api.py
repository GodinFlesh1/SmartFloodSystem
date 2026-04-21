import pytest
import respx
import httpx
from app.services.ea_api import (
    EnvironmentAgencyService,
    _snapshot_risk,
    _haversine,
)

EA_BASE = "https://environment.data.gov.uk/flood-monitoring"


# ── Pure function: _snapshot_risk ─────────────────────────────────────────────

def test_snapshot_risk_no_level():
    assert _snapshot_risk(None, 2.0, 0.5) == "NO_SENSOR"


def test_snapshot_risk_no_high():
    assert _snapshot_risk(1.5, None, 0.5) == "NORMAL"


def test_snapshot_risk_severe():
    assert _snapshot_risk(2.7, 2.0, 0.5) == "SEVERE"   # 2.7 >= 2.0 * 1.3


def test_snapshot_risk_high():
    assert _snapshot_risk(2.1, 2.0, 0.5) == "HIGH"     # 2.1 >= 2.0


def test_snapshot_risk_elevated():
    assert _snapshot_risk(1.6, 2.0, 0.5) == "ELEVATED" # 1.6 >= 2.0 * 0.75


def test_snapshot_risk_normal():
    assert _snapshot_risk(0.5, 2.0, 0.1) == "NORMAL"


# ── Pure function: _haversine ─────────────────────────────────────────────────

def test_haversine_same_point():
    assert _haversine(51.5, -0.1, 51.5, -0.1) == pytest.approx(0.0, abs=1e-6)


def test_haversine_london_to_manchester():
    dist = _haversine(51.5074, -0.1278, 53.4808, -2.2426)
    assert 255 < dist < 270


def test_haversine_symmetric():
    d1 = _haversine(51.0, -0.1, 52.0, -0.2)
    d2 = _haversine(52.0, -0.2, 51.0, -0.1)
    assert d1 == pytest.approx(d2, rel=1e-6)


# ── Async: get_all_stations ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_all_stations_success():
    with respx.mock(assert_all_called=False) as mock_respx:
        mock_respx.get(f"{EA_BASE}/id/stations").mock(
            return_value=httpx.Response(200, json={
                "items": [{"stationReference": "A", "label": "Station A"}]
            })
        )
        svc = EnvironmentAgencyService()
        result = await svc.get_all_stations(limit=1)

    assert result["success"] is True
    assert result["total_stations"] == 1


@pytest.mark.asyncio
async def test_get_all_stations_api_error():
    with respx.mock(assert_all_called=False) as mock_respx:
        mock_respx.get(f"{EA_BASE}/id/stations").mock(
            return_value=httpx.Response(503)
        )
        svc = EnvironmentAgencyService()
        result = await svc.get_all_stations()

    assert result["success"] is False
    assert "503" in result["error"]


@pytest.mark.asyncio
async def test_get_all_stations_network_error():
    with respx.mock(assert_all_called=False) as mock_respx:
        mock_respx.get(f"{EA_BASE}/id/stations").mock(
            side_effect=httpx.ConnectError("connection refused")
        )
        svc = EnvironmentAgencyService()
        result = await svc.get_all_stations()

    assert result["success"] is False


# ── Async: get_station_readings ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_station_readings_success():
    with respx.mock(assert_all_called=False) as mock_respx:
        mock_respx.get(f"{EA_BASE}/id/stations/ABC/readings").mock(
            return_value=httpx.Response(200, json={
                "items": [{"value": 1.2, "dateTime": "2024-06-01T12:00:00Z"}]
            })
        )
        svc = EnvironmentAgencyService()
        result = await svc.get_station_readings("ABC", limit=1)

    assert result["success"] is True
    assert result["readings_count"] == 1


@pytest.mark.asyncio
async def test_get_station_readings_not_found():
    with respx.mock(assert_all_called=False) as mock_respx:
        mock_respx.get(f"{EA_BASE}/id/stations/UNKNOWN/readings").mock(
            return_value=httpx.Response(404)
        )
        svc = EnvironmentAgencyService()
        result = await svc.get_station_readings("UNKNOWN")

    assert result["success"] is False
