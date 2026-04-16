"""
Flood prediction service — loads the trained XGBoost model and predicts
flood risk for a given location using live EA station data + real weather.

Lag features are computed from actual EA API readings (last 7 days),
not dummy values — this makes predictions accurate.
"""

import json
import asyncio
import joblib
import httpx
import numpy as np
from pathlib import Path
from datetime import date, timedelta
from typing import Dict, List, Optional

MODEL_PATH    = Path(__file__).parent.parent / "models" / "flood_model.pkl"
FEATURES_PATH = Path(__file__).parent.parent / "models" / "feature_columns.json"

EA_BASE      = "https://environment.data.gov.uk/flood-monitoring"
WEATHER_URL  = "https://api.open-meteo.com/v1/forecast"


class FloodPredictor:
    _model    = None
    _features: List[str] = []

    @classmethod
    def _load(cls):
        if cls._model is None:
            if not MODEL_PATH.exists():
                raise FileNotFoundError(
                    f"Model not found at {MODEL_PATH}\n"
                    "Train the model first: cd ai && python train.py"
                )
            cls._model    = joblib.load(MODEL_PATH)
            cls._features = json.loads(FEATURES_PATH.read_text())

    # ── Real historical readings ───────────────────────────────────────────────

    async def _fetch_station_history(
        self, client: httpx.AsyncClient, station_id: str
    ) -> Dict[str, float]:
        """
        Fetch last 7 days of readings for one station.
        Returns {date_str: max_level} — one value per day.
        """
        if not station_id:
            return {}
        start = (date.today() - timedelta(days=8)).isoformat()
        end   = date.today().isoformat()
        try:
            resp = await client.get(
                f"{EA_BASE}/id/stations/{station_id}/readings",
                params={"startdate": start, "enddate": end,
                        "_limit": 500, "_sorted": "true"},
                timeout=10,
            )
            if resp.status_code != 200:
                return {}
            items = resp.json().get("items", [])
        except Exception:
            return {}

        # Aggregate to daily max level
        daily: Dict[str, float] = {}
        for item in items:
            dt  = (item.get("dateTime") or "")[:10]
            val = item.get("value")
            if not dt or val is None:
                continue
            try:
                val = float(val)
                if dt not in daily or val > daily[dt]:
                    daily[dt] = val
            except (ValueError, TypeError):
                pass
        return daily

    # ── Weather ───────────────────────────────────────────────────────────────

    async def _fetch_weather(self, lat: float, lon: float) -> Dict:
        """Fetch last 14 days of weather aggregates from Open-Meteo forecast API."""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(WEATHER_URL, params={
                    "latitude":      round(lat, 4),
                    "longitude":     round(lon, 4),
                    "daily":         ",".join([
                        "precipitation_sum",
                        "rain_sum",
                        "wind_speed_10m_max",
                        "temperature_2m_max",
                        "temperature_2m_min",
                    ]),
                    "timezone":      "Europe/London",
                    "past_days":     14,
                    "forecast_days": 1,
                })
                resp.raise_for_status()
                daily = resp.json().get("daily", {})
        except Exception:
            # Neutral fallback — weather unavailable
            return {
                "precipitation_sum": 0.0, "rain_sum": 0.0,
                "wind_speed_10m_max": 5.0,
                "temperature_2m_max": 12.0, "temperature_2m_min": 6.0,
                "rain_3d": 0.0, "rain_7d": 0.0,
                "rain_14d": 0.0, "rain_lag_1d": 0.0,
            }

        precip   = daily.get("precipitation_sum", [])
        rain     = daily.get("rain_sum", [])
        wind     = daily.get("wind_speed_10m_max", [])
        temp_max = daily.get("temperature_2m_max", [])
        temp_min = daily.get("temperature_2m_min", [])

        def safe(lst, idx=-1, default=0.0):
            try:
                v = lst[idx]
                return float(v) if v is not None else default
            except (IndexError, TypeError):
                return default

        def safe_sum(lst, n):
            vals = [float(v) for v in lst[-n:] if v is not None]
            return sum(vals) if vals else 0.0

        return {
            "precipitation_sum":  safe(precip),
            "rain_sum":           safe(rain),
            "wind_speed_10m_max": safe(wind),
            "temperature_2m_max": safe(temp_max),
            "temperature_2m_min": safe(temp_min),
            "rain_3d":            safe_sum(precip, 3),
            "rain_7d":            safe_sum(precip, 7),
            "rain_14d":           safe_sum(precip, 14),
            "rain_lag_1d":        safe(precip, -2),
        }

    # ── Feature assembly ──────────────────────────────────────────────────────

    def _build_features(
        self,
        station: Dict,
        weather: Dict,
        history: Dict[str, float],
    ) -> Dict:
        level        = float(station.get("water_level") or 0.0)
        typical_high = float(
            station.get("typical_range_high")
            or station.get("typicalRangeHigh")
            or 1.0
        )
        lat = station.get("latitude", 0.0)
        lon = station.get("longitude", 0.0)

        today = date.today()

        # ── Real lag features from historical readings ─────────────────────────
        if history:
            sorted_dates = sorted(history.keys(), reverse=True)  # newest first

            def get_day(n: int) -> float:
                """Get level n days ago from sorted history."""
                target = (today - timedelta(days=n)).isoformat()
                # Try exact date first, then nearest available
                if target in history:
                    return history[target]
                if len(sorted_dates) > n:
                    return history[sorted_dates[n]]
                return level  # fallback to current

            level_1d      = get_day(1)
            level_3d      = get_day(3)
            level_7d      = get_day(7)
            level_roll_7d = (
                sum(history[d] for d in sorted_dates[:7]) / min(len(sorted_dates), 7)
            )
        else:
            # No history available — use current level (less accurate)
            level_1d = level_3d = level_7d = level_roll_7d = level

        return {
            # Current level
            "water_level":              level,
            "water_level_max":          max(level, max(history.values(), default=level)),
            "water_level_min":          min(level, min(history.values(), default=level)),
            # Lag features — real values
            "level_lag_1d":             level_1d,
            "level_lag_3d":             level_3d,
            "level_lag_7d":             level_7d,
            "level_change_1d":          level - level_1d,
            "level_change_3d":          level - level_3d,
            "level_roll_7d":            level_roll_7d,
            # Threshold proximity
            "level_above_typical_high": max(0.0, level - typical_high),
            "level_pct_lag_1d":         level_1d / typical_high if typical_high > 0 else 0.0,
            "level_pct_lag_3d":         level_3d / typical_high if typical_high > 0 else 0.0,
            # Weather
            **weather,
            # Calendar
            "month":       today.month,
            "day_of_year": today.timetuple().tm_yday,
            # Location
            "latitude":  lat,
            "longitude": lon,
        }

    # ── Prediction ────────────────────────────────────────────────────────────

    async def predict(self, lat: float, lon: float, stations: List[Dict]) -> Dict:
        self._load()

        if not stations:
            return {
                "success":    True,
                "risk_level": "UNKNOWN",
                "probability": 0.0,
                "confidence": "low",
                "reason":     "No nearby stations found.",
                "top_station": "",
                "station_predictions": [],
            }

        # Fetch weather + all station histories concurrently
        async with httpx.AsyncClient(timeout=15) as client:
            weather_task = self._fetch_weather(lat, lon)
            history_tasks = [
                self._fetch_station_history(client, s.get("ea_station_id", ""))
                for s in stations
            ]
            weather, *histories = await asyncio.gather(weather_task, *history_tasks)

        results = []
        for station, history in zip(stations, histories):
            features = self._build_features(station, weather, history)
            row = np.array([[features.get(f, 0.0) for f in self._features]])

            prob      = float(self._model.predict_proba(row)[0][1])
            predicted = int(self._model.predict(row)[0])

            results.append({
                "station_id":   station.get("ea_station_id", ""),
                "station_name": station.get("station_name", ""),
                "probability":  round(prob, 3),
                "flood_likely": predicted == 1,
                "water_level":  station.get("water_level"),
                "history_days": len(history),
            })

        results.sort(key=lambda x: x["probability"], reverse=True)
        top  = results[0]
        prob = top["probability"]

        if prob >= 0.75:
            risk_level = "SEVERE";  confidence = "high"
        elif prob >= 0.55:
            risk_level = "HIGH";    confidence = "high"
        elif prob >= 0.35:
            risk_level = "MODERATE"; confidence = "medium"
        elif prob >= 0.15:
            risk_level = "MINIMAL"; confidence = "low"
        else:
            risk_level = "NORMAL";  confidence = "high"

        reason = _build_reason(risk_level, weather, top["station_name"])

        return {
            "success":             True,
            "risk_level":          risk_level,
            "probability":         round(prob, 3),
            "confidence":          confidence,
            "reason":              reason,
            "top_station":         top["station_name"],
            "station_predictions": results[:5],
        }


def _build_reason(risk_level: str, weather: Dict, station_name: str) -> str:
    rain3 = weather.get("rain_3d", 0)
    rain7 = weather.get("rain_7d", 0)

    if risk_level == "NORMAL":
        return "Water levels and rainfall are within normal ranges. No flood risk expected."
    if risk_level == "MINIMAL":
        return f"Slightly elevated conditions near {station_name}. Monitor local updates."
    if risk_level == "MODERATE":
        parts = [f"Moderate flood risk detected near {station_name}."]
        if rain3 > 15:
            parts.append(f"{rain3:.0f}mm of rain in the last 3 days.")
        parts.append("Stay aware of local flood warnings.")
        return " ".join(parts)
    if risk_level == "HIGH":
        parts = [f"High flood risk near {station_name}."]
        if rain7 > 30:
            parts.append(f"{rain7:.0f}mm of rain in the last 7 days.")
        parts.append("Avoid low-lying and flood-prone areas.")
        return " ".join(parts)
    if risk_level == "SEVERE":
        return (
            f"Severe flood risk near {station_name}. "
            f"{rain7:.0f}mm of rain in the last 7 days. "
            "Immediate action may be required — follow official guidance."
        )
    return "Flood risk assessment unavailable."
