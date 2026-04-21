from fastapi import APIRouter
from app.dependencies import risk_calc
from app.database.db import get_all_stations_from_db

router = APIRouter(prefix="/api", tags=["Alerts"])


@router.get("/alerts")
async def get_active_alerts():
    """Assess risk for all DB stations and return those with HIGH or CRITICAL level."""
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
