from app.services.notification_service import (
    _worst_station,
    send_fcm_to_token,
    send_fcm_multicast,
    _RISK_ORDER,
)


# ── _worst_station ─────────────────────────────────────────────────────────────

def test_worst_station_all_normal():
    stations = [
        {"risk_level": "NORMAL", "station_name": "A"},
        {"risk_level": "NO_SENSOR", "station_name": "B"},
    ]
    assert _worst_station(stations) is None


def test_worst_station_picks_highest():
    stations = [
        {"risk_level": "HIGH",   "station_name": "A"},
        {"risk_level": "SEVERE", "station_name": "B"},
        {"risk_level": "NORMAL", "station_name": "C"},
    ]
    result = _worst_station(stations)
    assert result["station_name"] == "B"
    assert result["risk_level"] == "SEVERE"


def test_worst_station_single_high():
    stations = [{"risk_level": "HIGH", "station_name": "X"}]
    result = _worst_station(stations)
    assert result["risk_level"] == "HIGH"


def test_worst_station_empty():
    assert _worst_station([]) is None


def test_worst_station_ignores_elevated():
    stations = [{"risk_level": "ELEVATED", "station_name": "E"}]
    assert _worst_station(stations) is None


# ── Risk order sanity ──────────────────────────────────────────────────────────

def test_risk_order_values():
    assert _RISK_ORDER["NO_SENSOR"] < _RISK_ORDER["NORMAL"]
    assert _RISK_ORDER["NORMAL"]    < _RISK_ORDER["ELEVATED"]
    assert _RISK_ORDER["ELEVATED"]  < _RISK_ORDER["HIGH"]
    assert _RISK_ORDER["HIGH"]      < _RISK_ORDER["SEVERE"]


# ── send_fcm_to_token when Firebase not initialised ───────────────────────────

def test_send_fcm_to_token_firebase_not_init():
    # Firebase is never initialised in the test env — should silently return False
    result = send_fcm_to_token("fake-token", "Title", "Body")
    assert result is False


def test_send_fcm_multicast_firebase_not_init():
    result = send_fcm_multicast(["tok1", "tok2"], "Title", "Body")
    assert result == 0


def test_send_fcm_multicast_empty_tokens():
    result = send_fcm_multicast([], "Title", "Body")
    assert result == 0
