import pytest
from datetime import date
from app.services.flood_predictor import FloodPredictor, _build_reason


# ── _build_reason ─────────────────────────────────────────────────────────────

def test_build_reason_normal():
    r = _build_reason("NORMAL", {"rain_3d": 0, "rain_7d": 0}, "Station X")
    assert "No flood risk" in r


def test_build_reason_minimal():
    r = _build_reason("MINIMAL", {"rain_3d": 0, "rain_7d": 0}, "Station X")
    assert "Station X" in r
    assert "Monitor" in r


def test_build_reason_moderate_high_rain():
    r = _build_reason("MODERATE", {"rain_3d": 20, "rain_7d": 10}, "Station X")
    assert "20mm" in r
    assert "Station X" in r


def test_build_reason_moderate_low_rain():
    r = _build_reason("MODERATE", {"rain_3d": 5, "rain_7d": 0}, "Station X")
    # No rain figure injected when rain3 <= 15
    assert "Station X" in r


def test_build_reason_high_with_rain():
    r = _build_reason("HIGH", {"rain_3d": 10, "rain_7d": 40}, "Station X")
    assert "40mm" in r
    assert "Avoid" in r


def test_build_reason_severe():
    r = _build_reason("SEVERE", {"rain_3d": 10, "rain_7d": 55}, "Station X")
    assert "Severe" in r
    assert "55mm" in r


def test_build_reason_unknown_level():
    r = _build_reason("UNKNOWN_LEVEL", {"rain_3d": 0, "rain_7d": 0}, "X")
    assert "unavailable" in r


# ── _build_features ───────────────────────────────────────────────────────────

def test_build_features_with_history():
    predictor = FloodPredictor()
    today = date.today()
    history = {
        (today).isoformat():                    1.5,
        (today.replace(day=today.day - 1) if today.day > 1 else today).isoformat(): 1.3,
    }
    station = {
        "water_level": 1.5,
        "typical_range_high": 2.0,
        "latitude": 51.5,
        "longitude": -0.1,
    }
    weather = {
        "precipitation_sum": 5.0, "rain_sum": 4.0,
        "wind_speed_10m_max": 10.0,
        "temperature_2m_max": 15.0, "temperature_2m_min": 8.0,
        "rain_3d": 12.0, "rain_7d": 25.0,
        "rain_14d": 40.0, "rain_lag_1d": 3.0,
    }
    features = predictor._build_features(station, weather, history)

    assert features["water_level"] == 1.5
    assert features["latitude"] == 51.5
    assert features["level_above_typical_high"] == pytest.approx(0.0)  # 1.5 < 2.0
    assert features["month"] == today.month


def test_build_features_no_history():
    predictor = FloodPredictor()
    station = {
        "water_level": 1.0,
        "typical_range_high": 2.0,
        "latitude": 52.0,
        "longitude": -1.0,
    }
    weather = {
        "precipitation_sum": 0, "rain_sum": 0,
        "wind_speed_10m_max": 5, "temperature_2m_max": 12,
        "temperature_2m_min": 6, "rain_3d": 0,
        "rain_7d": 0, "rain_14d": 0, "rain_lag_1d": 0,
    }
    features = predictor._build_features(station, weather, {})

    # With no history, lag features fall back to current level
    assert features["level_lag_1d"] == 1.0
    assert features["level_change_1d"] == pytest.approx(0.0)


def test_build_features_above_typical_high():
    predictor = FloodPredictor()
    station = {"water_level": 2.5, "typical_range_high": 2.0, "latitude": 0, "longitude": 0}
    features = predictor._build_features(station, {
        "precipitation_sum": 0, "rain_sum": 0, "wind_speed_10m_max": 0,
        "temperature_2m_max": 0, "temperature_2m_min": 0,
        "rain_3d": 0, "rain_7d": 0, "rain_14d": 0, "rain_lag_1d": 0,
    }, {})

    assert features["level_above_typical_high"] == pytest.approx(0.5)
