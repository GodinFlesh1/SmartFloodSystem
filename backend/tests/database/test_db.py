import pytest
from unittest.mock import MagicMock, patch
from app.database.db import (
    _haversine,
    find_nearby_stations,
    store_station,
    get_station_by_ea_id,
    get_all_stations_from_db,
    store_reading,
    get_latest_reading_for_station,
    get_readings_history,
)


# ── Pure function: _haversine ─────────────────────────────────────────────────

def test_haversine_zero_distance():
    assert _haversine(51.5, -0.1, 51.5, -0.1) == pytest.approx(0.0, abs=1e-6)


def test_haversine_london_manchester():
    dist = _haversine(51.5074, -0.1278, 53.4808, -2.2426)
    assert 255 < dist < 270


# ── find_nearby_stations ──────────────────────────────────────────────────────

def _make_mock_sb(stations: list):
    mock_sb = MagicMock()
    result = MagicMock()
    result.data = stations
    mock_sb.table.return_value.select.return_value.execute.return_value = result
    return mock_sb


@pytest.mark.asyncio
async def test_find_nearby_stations_filters_by_radius():
    stations = [
        {"id": "1", "latitude": 51.5,  "longitude": -0.1,  "station_name": "Close"},    # ~0 km
        {"id": "2", "latitude": 52.0,  "longitude": -0.1,  "station_name": "Far"},      # ~55 km
        {"id": "3", "latitude": 51.51, "longitude": -0.09, "station_name": "Nearby"},   # ~1.5 km
    ]
    with patch("app.database.db.supabase", _make_mock_sb(stations)):
        result = await find_nearby_stations(51.5, -0.1, radius_km=10)

    names = [s["station_name"] for s in result]
    assert "Close" in names
    assert "Nearby" in names
    assert "Far" not in names


@pytest.mark.asyncio
async def test_find_nearby_stations_sorted_by_distance():
    stations = [
        {"id": "1", "latitude": 51.52, "longitude": -0.1, "station_name": "A"},
        {"id": "2", "latitude": 51.51, "longitude": -0.1, "station_name": "B"},
    ]
    with patch("app.database.db.supabase", _make_mock_sb(stations)):
        result = await find_nearby_stations(51.5, -0.1, radius_km=10)

    assert result[0]["station_name"] == "B"  # B is closer


@pytest.mark.asyncio
async def test_find_nearby_stations_empty_db():
    with patch("app.database.db.supabase", _make_mock_sb([])):
        result = await find_nearby_stations(51.5, -0.1)
    assert result == []


# ── store_station ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_store_station_success():
    stored = {"id": "uuid-1", "ea_station_id": "ABC", "station_name": "Test"}
    mock_sb = MagicMock()
    mock_sb.table.return_value.upsert.return_value.execute.return_value.data = [stored]

    with patch("app.database.db.supabase", mock_sb):
        result = await store_station({
            "stationReference": "ABC",
            "label": "Test",
            "lat": 51.5,
            "long": -0.1,
            "town": "London",
            "riverName": "Thames",
        })

    assert result == stored


@pytest.mark.asyncio
async def test_store_station_db_error_returns_none():
    mock_sb = MagicMock()
    mock_sb.table.return_value.upsert.return_value.execute.side_effect = Exception("DB error")

    with patch("app.database.db.supabase", mock_sb):
        result = await store_station({"stationReference": "ABC"})

    assert result is None


# ── get_station_by_ea_id ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_station_by_ea_id_found():
    row = {"id": "uuid-1", "ea_station_id": "ABC"}
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [row]

    with patch("app.database.db.supabase", mock_sb):
        result = await get_station_by_ea_id("ABC")

    assert result == row


@pytest.mark.asyncio
async def test_get_station_by_ea_id_not_found():
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

    with patch("app.database.db.supabase", mock_sb):
        result = await get_station_by_ea_id("UNKNOWN")

    assert result is None


# ── store_reading ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_store_reading_success():
    row = {"id": "r1", "station_id": "s1", "water_level": 1.2}
    mock_sb = MagicMock()
    mock_sb.table.return_value.insert.return_value.execute.return_value.data = [row]

    with patch("app.database.db.supabase", mock_sb):
        result = await store_reading("s1", "ABC", {"value": 1.2, "dateTime": "2024-06-01T12:00:00Z"})

    assert result == row


# ── get_readings_history ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_readings_history_oldest_first():
    readings = [
        {"water_level": 1.3, "timestamp": "2024-06-01T14:00:00"},
        {"water_level": 1.2, "timestamp": "2024-06-01T13:00:00"},
        {"water_level": 1.1, "timestamp": "2024-06-01T12:00:00"},
    ]
    mock_sb = MagicMock()
    chain = mock_sb.table.return_value
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    chain.execute.return_value.data = list(readings)  # desc order from DB

    with patch("app.database.db.supabase", mock_sb):
        result = await get_readings_history("s1", limit=3)

    # Function reverses the list so oldest is first
    assert result[0]["timestamp"] == "2024-06-01T12:00:00"
    assert result[-1]["timestamp"] == "2024-06-01T14:00:00"
