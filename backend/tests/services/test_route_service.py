import pytest
import respx
import httpx
from app.services.route_service import RouteService, _haversine, _decode_polyline


# ── Pure functions ─────────────────────────────────────────────────────────────

def test_haversine_same_point():
    assert _haversine(51.5, -0.1, 51.5, -0.1) == pytest.approx(0.0, abs=1e-6)


def test_haversine_known_distance():
    dist = _haversine(51.5074, -0.1278, 53.4808, -2.2426)
    assert 255 < dist < 270


def test_decode_polyline_empty():
    assert _decode_polyline("") == []


def test_decode_polyline_known():
    # "_p~iF~ps|U_ulLnnqC_mqNvxq`@" is a well-known polyline test vector
    coords = _decode_polyline("_p~iF~ps|U_ulLnnqC_mqNvxq`@")
    assert len(coords) == 3
    assert coords[0][0] == pytest.approx(38.5, abs=0.01)
    assert coords[0][1] == pytest.approx(-120.2, abs=0.01)


# ── get_safe_places ────────────────────────────────────────────────────────────

OVERPASS_URL = "https://overpass-api.de/api/interpreter"


@pytest.mark.asyncio
async def test_get_safe_places_returns_sorted_list():
    elements = [
        {"tags": {"name": "Far Hall", "amenity": "community_centre"},
         "lat": 51.52, "lon": -0.08},
        {"tags": {"name": "Near School", "amenity": "school"},
         "lat": 51.505, "lon": -0.102},
    ]
    with respx.mock(assert_all_called=False) as mock_respx:
        mock_respx.post(OVERPASS_URL).mock(
            return_value=httpx.Response(200, json={"elements": elements})
        )
        svc = RouteService()
        places = await svc.get_safe_places(lat=51.5, lon=-0.1, radius_m=5000)

    assert len(places) == 2
    assert places[0]["name"] == "Near School"
    assert places[0]["type"] == "school"


@pytest.mark.asyncio
async def test_get_safe_places_skips_missing_coords():
    with respx.mock(assert_all_called=False) as mock_respx:
        mock_respx.post(OVERPASS_URL).mock(
            return_value=httpx.Response(200, json={
                "elements": [
                    {"tags": {"amenity": "school"}, "lat": None, "lon": None},
                ]
            })
        )
        svc = RouteService()
        places = await svc.get_safe_places(51.5, -0.1)

    assert places == []


@pytest.mark.asyncio
async def test_get_safe_places_api_error_returns_empty():
    with respx.mock(assert_all_called=False) as mock_respx:
        mock_respx.post(OVERPASS_URL).mock(
            side_effect=httpx.ConnectError("timeout")
        )
        svc = RouteService()
        places = await svc.get_safe_places(51.5, -0.1)

    assert places == []


# ── get_route ──────────────────────────────────────────────────────────────────

ORS_BASE = "https://api.openrouteservice.org"


@pytest.mark.asyncio
async def test_get_route_no_api_key(monkeypatch):
    monkeypatch.setenv("ORS_API_KEY", "")
    svc = RouteService()
    result = await svc.get_route(51.5, -0.1, 51.51, -0.09)
    assert result["success"] is False
    assert "key" in result["error"].lower()


@pytest.mark.asyncio
async def test_get_route_success(monkeypatch):
    monkeypatch.setenv("ORS_API_KEY", "test-key")
    fake_response = {
        "routes": [{
            "summary": {"distance": 800.0, "duration": 120.0},
            "segments": [{"steps": [
                {"instruction": "Head north", "distance": 800.0, "duration": 120.0}
            ]}],
            "geometry": "_p~iF~ps|U_ulLnnqC_mqNvxq`@",
        }]
    }
    with respx.mock(assert_all_called=False) as mock_respx:
        mock_respx.post(f"{ORS_BASE}/v2/directions/driving-car").mock(
            return_value=httpx.Response(200, json=fake_response)
        )
        svc = RouteService()
        result = await svc.get_route(51.5, -0.1, 51.51, -0.09)

    assert result["success"] is True
    assert result["distance_m"] == 800
    assert len(result["steps"]) == 1
    assert result["steps"][0]["instruction"] == "Head north"


# ── get_safe_route_to_shelter ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_safe_route_no_shelters():
    with respx.mock(assert_all_called=False) as mock_respx:
        mock_respx.post(OVERPASS_URL).mock(
            return_value=httpx.Response(200, json={"elements": []})
        )
        svc = RouteService()
        result = await svc.get_safe_route_to_shelter(51.5, -0.1)

    assert result["success"] is False
    assert "No safe shelters" in result["error"]
