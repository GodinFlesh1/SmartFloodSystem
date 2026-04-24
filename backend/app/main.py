import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Query, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.auth import init_firebase, verify_token, verify_token_no_device, require_google_admin
from app.services.ea_api import EnvironmentAgencyService
from app.services.risk_calculator import RiskCalculator
from app.services.flood_predictor import FloodPredictor
from app.services.route_service import RouteService
from app.database.db import (
    store_station,
    get_all_stations_from_db,
    find_nearby_stations,
    get_latest_reading_for_station,
    get_readings_history,
)

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_firebase()
    yield


app = FastAPI(
    title="EcoFlood API",
    description="Real-time flood monitoring and early-warning system",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

_origins_env = os.getenv("ALLOWED_ORIGINS", "*")
_allowed_origins = (
    ["*"] if _origins_env.strip() == "*"
    else [o.strip() for o in _origins_env.split(",") if o.strip()]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-Device-ID"],
)

ea_service    = EnvironmentAgencyService()
risk_calc     = RiskCalculator()
predictor     = FloodPredictor()
route_service = RouteService()

# ── HEALTH (no auth — always public) ──────────────────────────────────────────

@app.get("/")
async def root():
    return {"message": "EcoFlood API is running", "status": "healthy", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    return {"status": "ok"}

# ── ADMIN PANEL ───────────────────────────────────────────────────────────────

_ADMIN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>EcoFlood Admin</title>
  <style>
    body { font-family: sans-serif; max-width: 600px; margin: 60px auto; padding: 0 20px; background: #f0f4f8; }
    h1   { color: #0D47A1; }
    .card { background: white; border-radius: 12px; padding: 24px; box-shadow: 0 2px 8px rgba(0,0,0,.1); margin-bottom: 16px; }
    button { background: #1565C0; color: white; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer; margin: 4px; font-size: 14px; }
    button:hover { background: #0D47A1; }
    #logout-btn { background: #c62828; }
    #status { margin-top: 12px; white-space: pre-wrap; font-size: 13px; color: #333; background: #e8eaf6; padding: 12px; border-radius: 8px; display:none; }
    #panel { display:none; }
    .email { color: #1565C0; font-weight: bold; }
  </style>
</head>
<body>
  <div class="card">
    <h1>EcoFlood Admin</h1>

    <div id="login-section">
      <p>Sign in with your authorised Gmail account to access admin controls.</p>
      <button id="google-btn">Sign in with Google</button>
    </div>

    <div id="panel">
      <p>Signed in as <span class="email" id="email-label"></span></p>
      <button id="logout-btn">Sign Out</button>
    </div>
  </div>

  <div class="card" id="panel-actions" style="display:none">
    <h2>Sync Controls</h2>
    <button onclick="syncStations()">Sync Stations (100)</button>
    <div id="status"></div>
  </div>

  <script type="module">
    import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.0/firebase-app.js";
    import { getAuth, GoogleAuthProvider, signInWithPopup, signOut, onAuthStateChanged }
      from "https://www.gstatic.com/firebasejs/10.12.0/firebase-auth.js";

    const app  = initializeApp({
      apiKey:    "AIzaSyCq0aDFCFb6HErfnyq4iaX2OeNUVIZ2m5g",
      authDomain:"smartfloodsys.firebaseapp.com",
      projectId: "smartfloodsys",
      appId:     "1:415217552470:web:85ac421c811eb1bd3fbff7",
    });
    const auth     = getAuth(app);
    const provider = new GoogleAuthProvider();

    document.getElementById("google-btn").onclick = () => signInWithPopup(auth, provider);
    document.getElementById("logout-btn").onclick  = () => signOut(auth);

    onAuthStateChanged(auth, user => {
      const loggedIn = !!user;
      document.getElementById("login-section").style.display   = loggedIn ? "none"  : "block";
      document.getElementById("panel").style.display            = loggedIn ? "block" : "none";
      document.getElementById("panel-actions").style.display    = loggedIn ? "block" : "none";
      if (user) document.getElementById("email-label").textContent = user.email;
    });

    async function getToken() {
      const user = auth.currentUser;
      if (!user) throw new Error("Not signed in");
      return user.getIdToken();
    }

    window.syncStations = async () => {
      const status = document.getElementById("status");
      status.style.display = "block";
      status.textContent = "Syncing...";
      try {
        const token = await getToken();
        const res   = await fetch("/api/sync/stations?limit=100", {
          method: "POST",
          headers: { Authorization: "Bearer " + token },
        });
        const data = await res.json();
        status.textContent = res.ok
          ? "Done — fetched: " + data.fetched + ", stored: " + data.stored
          : "Error " + res.status + ": " + JSON.stringify(data);
      } catch (e) {
        status.textContent = "Error: " + e.message;
      }
    };
  </script>
</body>
</html>"""


@app.get("/admin", response_class=HTMLResponse, include_in_schema=False)
async def admin_panel():
    """Browser-based admin panel — sign in with an authorised Gmail to access sync controls."""
    return _ADMIN_HTML

# ── AUTH ─────────────────────────────────────────────────────────────────────

class _DeviceBody(BaseModel):
    device_id: str


@app.post("/api/auth/register-device")
@limiter.limit("10/minute")
async def register_device_endpoint(
    request: Request,
    body: _DeviceBody,
    user: dict = Depends(verify_token_no_device),
):
    """
    Register or update the device bound to this Firebase UID.
    Uses verify_token_no_device so users can re-register when switching phones.
    """
    from app.database.db import register_device
    await register_device(user["uid"], body.device_id)
    return {"success": True}

# ── LIVE EA API ────────────────────────────────────────────────────────────────

@app.get("/api/live/stations/nearby")
@limiter.limit("60/minute")
async def live_nearby_stations(
    request: Request,
    lat: float = Query(..., description="Latitude", ge=-90, le=90, example=51.5074),
    lon: float = Query(..., description="Longitude", ge=-180, le=180, example=-0.1278),
    radius_km: float = Query(10, description="Search radius km", ge=0.1, le=100),
    _user: dict = Depends(verify_token),
):
    result = await ea_service.get_nearby_stations_live(lat, lon, radius_km)
    if result.get("success"):
        result["user_location"] = {"lat": lat, "lon": lon}
    return result


@app.get("/api/ea/stations")
@limiter.limit("60/minute")
async def get_ea_stations(
    request: Request,
    limit: int = Query(50, ge=1, le=500),
    _user: dict = Depends(verify_token),
):
    return await ea_service.get_all_stations(limit)


@app.get("/api/ea/stations/{station_id}/readings")
@limiter.limit("60/minute")
async def get_ea_readings(
    request: Request,
    station_id: str,
    limit: int = Query(24, ge=1, le=96),
    _user: dict = Depends(verify_token),
):
    return await ea_service.get_station_readings(station_id, limit)


@app.get("/api/ea/stations/{station_id}/latest")
@limiter.limit("60/minute")
async def get_station_latest(
    request: Request,
    station_id: str,
    _user: dict = Depends(verify_token),
):
    return await ea_service.get_station_latest_all_measures(station_id)

# ── DB SYNC (reserved for large-scale deployment) ─────────────────────────────

@app.post("/api/sync/stations")
@limiter.limit("5/minute")
async def sync_stations(
    request: Request,
    limit: int = Query(100, ge=1, le=500),
    _user: dict = Depends(require_google_admin),
):
    result = await ea_service.get_all_stations(limit)
    if not result.get("success"):
        return {"success": False, "error": result.get("error")}
    stations = result.get("stations", [])
    stored_count = 0
    errors = []
    for s in stations:
        try:
            stored = await store_station(s)
            if stored:
                stored_count += 1
        except Exception as e:
            errors.append(str(e))
    return {
        "success": True,
        "fetched": len(stations),
        "stored": stored_count,
        "errors": errors or None,
    }


@app.post("/api/sync/readings/{station_id}")
@limiter.limit("5/minute")
async def sync_readings(
    request: Request,
    station_id: str,
    _user: dict = Depends(require_google_admin),
):
    return await ea_service.fetch_and_store_readings(station_id)

# ── DB QUERY (reserved for large-scale deployment) ────────────────────────────

@app.get("/api/database/stations")
@limiter.limit("60/minute")
async def get_db_stations(
    request: Request,
    _user: dict = Depends(verify_token),
):
    stations = await get_all_stations_from_db()
    return {"success": True, "count": len(stations), "stations": stations}


@app.get("/api/stations/nearby")
@limiter.limit("60/minute")
async def get_nearby_stations(
    request: Request,
    lat: float = Query(..., ge=-90, le=90, example=51.5074),
    lon: float = Query(..., ge=-180, le=180, example=-0.1278),
    radius_km: float = Query(10, ge=0.1, le=100),
    _user: dict = Depends(verify_token),
):
    stations = await find_nearby_stations(lat, lon, radius_km)
    for s in stations:
        s["latest_reading"] = await get_latest_reading_for_station(s["id"])
    return {
        "success": True,
        "user_location": {"lat": lat, "lon": lon},
        "radius_km": radius_km,
        "stations_found": len(stations),
        "stations": stations,
    }

# ── RISK ASSESSMENT ───────────────────────────────────────────────────────────

@app.get("/api/stations/{station_id}/risk")
@limiter.limit("10/minute")
async def get_station_risk(
    request: Request,
    station_id: str,
    _user: dict = Depends(verify_token),
):
    return await risk_calc.assess_risk(station_id)


@app.get("/api/stations/{station_id}/readings/history")
@limiter.limit("60/minute")
async def get_station_readings_history(
    request: Request,
    station_id: str,
    limit: int = Query(48, description="Number of readings (max 96)", ge=1, le=96),
    _user: dict = Depends(verify_token),
):
    readings = await get_readings_history(station_id, limit)
    return {"success": True, "station_id": station_id, "count": len(readings), "readings": readings}

# ── ALERTS ────────────────────────────────────────────────────────────────────

@app.get("/api/alerts")
@limiter.limit("10/minute")
async def get_active_alerts(
    request: Request,
    _user: dict = Depends(verify_token),
):
    stations = await get_all_stations_from_db()
    alerts = []
    for s in stations:
        risk = await risk_calc.assess_risk(s["id"])
        if risk["risk_level"] in ("HIGH", "CRITICAL"):
            alerts.append({
                **risk,
                "station_name": s["station_name"],
                "town": s.get("town"),
                "river_name": s.get("river_name"),
                "latitude": s.get("latitude"),
                "longitude": s.get("longitude"),
            })
    return {"success": True, "alert_count": len(alerts), "alerts": alerts}

# ── FLOOD MAP ─────────────────────────────────────────────────────────────────

@app.get("/api/flood-map")
@limiter.limit("60/minute")
async def get_flood_map(
    request: Request,
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    radius_km: float = Query(25, ge=0.1, le=100),
    _user: dict = Depends(verify_token),
):
    result = await ea_service.get_nearby_stations_live(lat, lon, radius_km)
    if not result.get("success"):
        return result

    map_points = [
        {
            "ea_station_id": s["ea_station_id"],
            "station_name": s["station_name"],
            "latitude": s["latitude"],
            "longitude": s["longitude"],
            "town": s.get("town"),
            "river_name": s.get("river_name"),
            "water_level": s.get("water_level"),
            "risk_level": s.get("risk_level", "UNKNOWN"),
            "distance_km": s.get("distance_km"),
        }
        for s in result["stations"]
        if s.get("latitude") and s.get("longitude")
    ]

    return {
        "success": True,
        "center": {"lat": lat, "lon": lon},
        "radius_km": radius_km,
        "point_count": len(map_points),
        "points": map_points,
    }

# ── AI FLOOD PREDICTION ───────────────────────────────────────────────────────

@app.get("/api/predict/flood-risk")
@limiter.limit("10/minute")
async def predict_flood_risk(
    request: Request,
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    radius_km: float = Query(10, ge=0.1, le=100),
    _user: dict = Depends(verify_token),
):
    stations_result = await ea_service.get_nearby_stations_live(lat, lon, radius_km)
    if not stations_result.get("success"):
        return {"success": False, "error": "Could not fetch nearby stations"}
    stations = stations_result.get("stations", [])
    return await predictor.predict(lat, lon, stations)

# ── SAFE ROUTES ───────────────────────────────────────────────────────────────

@app.get("/api/safe-places")
@limiter.limit("60/minute")
async def get_safe_places(
    request: Request,
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    radius_m: int = Query(5000, ge=100, le=50000),
    _user: dict = Depends(verify_token),
):
    places = await route_service.get_safe_places(lat, lon, radius_m)
    return {"success": True, "count": len(places), "places": places}


@app.get("/api/safe-route")
@limiter.limit("30/minute")
async def get_safe_route(
    request: Request,
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    radius_m: int = Query(5000, ge=100, le=50000),
    profile: str = Query("driving-car", description="driving-car | foot-walking"),
    _user: dict = Depends(verify_token),
):
    return await route_service.get_safe_route_to_shelter(
        lat=lat, lon=lon, radius_m=radius_m, profile=profile
    )


@app.get("/api/route")
@limiter.limit("30/minute")
async def get_direct_route(
    request: Request,
    from_lat: float = Query(..., ge=-90, le=90),
    from_lon: float = Query(..., ge=-180, le=180),
    to_lat: float = Query(..., ge=-90, le=90),
    to_lon: float = Query(..., ge=-180, le=180),
    profile: str = Query("driving-car", description="driving-car | foot-walking"),
    _user: dict = Depends(verify_token),
):
    return await route_service.get_route(
        from_lat=from_lat, from_lon=from_lon,
        to_lat=to_lat, to_lon=to_lon,
        profile=profile,
    )
