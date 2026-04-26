"""
Flood prediction service — loads the calibrated XGBoost model and predicts
flood risk for a location using live EA station data + current/forecast weather.

Design notes matching the training pipeline:
  - Lag features come from real EA historical readings (past ~30 days)
  - Rainfall features include both past (rain_past_Nd) AND future forecast
    (rain_next_Nd), fetched via Open-Meteo's forecast_days parameter
  - Every station always produces a prediction. typical_range_high is
    resolved from EA stageScale when available, inferred from recent history
    when not, and finally falls back to a generic default — in which case
    the score is blended toward a pure rainfall-driven baseline
  - Risk bands are anchored to the saved decision_threshold.json so thresholds
    stay aligned with what the model was tuned for
  - A rule-based sanity gate overrides the model when rain is negligible AND
    water level is well below threshold — protects against residual bias
"""

import json
import asyncio
import joblib
import httpx
import numpy as np
from cachetools import TTLCache
from pathlib import Path
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

MODEL_PATH     = Path(__file__).parent.parent / "models" / "flood_model.pkl"
FEATURES_PATH  = Path(__file__).parent.parent / "models" / "feature_columns.json"
THRESHOLD_PATH = Path(__file__).parent.parent / "models" / "decision_threshold.json"

EA_BASE     = "https://environment.data.gov.uk/flood-monitoring"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"

# ── Module-level caches (survive across requests in the same process) ─────────
_history_cache: TTLCache = TTLCache(maxsize=500, ttl=1800)   # per station_id, 30 min
_meta_cache:    TTLCache = TTLCache(maxsize=500, ttl=86400)  # per station_id, 24 hr
_weather_cache: TTLCache = TTLCache(maxsize=100, ttl=7200)   # per location, 2 hr

# Fallback risk thresholds if decision_threshold.json is missing.
# Absolute calibrated-probability cuts — these are the numbers the UI bands
# show to the user. Changing them is a policy decision, not a modelling one.
DEFAULT_DECISION_THRESHOLD = 0.50
DEFAULT_BANDS = {
    "severe":   0.60,
    "high":     0.40,
    "moderate": 0.20,
    "minimal":  0.08,
}


class FloodPredictor:
    _model = None
    _features: List[str] = []
    _decision_threshold: float = DEFAULT_DECISION_THRESHOLD
    _bands: Dict = DEFAULT_BANDS

    @classmethod
    def _load(cls):
        if cls._model is not None:
            return
        if not MODEL_PATH.exists():
            raise FileNotFoundError(
                f"Model not found at {MODEL_PATH}\n"
                "Train the model first: cd ai && python train.py"
            )
        cls._model    = joblib.load(MODEL_PATH)
        cls._features = json.loads(FEATURES_PATH.read_text())
        if THRESHOLD_PATH.exists():
            payload = json.loads(THRESHOLD_PATH.read_text())
            cls._decision_threshold = float(payload.get("decision_threshold", DEFAULT_DECISION_THRESHOLD))
            cls._bands = payload.get("risk_bands", DEFAULT_BANDS)

    # ── Station metadata (typicalRangeHigh) ─────────────────────────────────

    async def _fetch_station_meta(
        self, client: httpx.AsyncClient, station_id: str
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Fetch (typicalRangeHigh, typicalRangeLow) from the individual station
        endpoint. The stations-list endpoint returns stageScale as a URL string
        not an embedded object, so typical_range_high is always None there.
        Cached 24 hr — this data almost never changes.
        """
        if not station_id:
            return None, None
        if station_id in _meta_cache:
            return _meta_cache[station_id]
        try:
            r = await client.get(f"{EA_BASE}/id/stations/{station_id}", timeout=8)
            if r.status_code != 200:
                result = (None, None)
            else:
                item = r.json().get("items", {})
                if isinstance(item, list):
                    item = item[0] if item else {}
                stage = item.get("stageScale") or {}
                if isinstance(stage, str):
                    result = (None, None)
                else:
                    result = (stage.get("typicalRangeHigh"), stage.get("typicalRangeLow"))
        except Exception:
            result = (None, None)
        _meta_cache[station_id] = result
        return result

    # ── Real historical readings ──────────────────────────────────────────────

    async def _fetch_station_history(
        self, client: httpx.AsyncClient, station_id: str
    ) -> Dict[str, float]:
        """
        Fetch last ~30 days of readings for one station. A longer window lets us
        infer a plausible typical_range_high for stations that don't report it.
        Returns {date_str: max_level} — one value per day. Cached 30 min.
        """
        if not station_id:
            return {}
        if station_id in _history_cache:
            return _history_cache[station_id]
        start = (date.today() - timedelta(days=30)).isoformat()
        end   = date.today().isoformat()
        try:
            resp = await client.get(
                f"{EA_BASE}/id/stations/{station_id}/readings",
                params={"startdate": start, "enddate": end,
                        "_limit": 1000, "_sorted": "true"},
                timeout=10,
            )
            if resp.status_code != 200:
                return {}
            items = resp.json().get("items", [])
        except Exception:
            return {}

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
        _history_cache[station_id] = daily
        return daily

    # ── Weather — past + future forecast ───────────────────────────────────────

    async def _fetch_weather(self, lat: float, lon: float) -> Optional[Dict]:
        """
        Fetch past 14 days + next 3 days of daily weather. Cached 2 hr per
        0.02-degree grid cell (~2 km). Returns None if the API fails.
        """
        cache_key = (round(lat, 2), round(lon, 2))
        if cache_key in _weather_cache:
            return _weather_cache[cache_key]
        params = {
            "latitude":      round(lat, 4),
            "longitude":     round(lon, 4),
            "daily":         "precipitation_sum,wind_speed_10m_max,temperature_2m_max,temperature_2m_min",
            "timezone":      "Europe/London",
            "past_days":     14,
            "forecast_days": 4,
        }
        payload = {}
        last_err = None
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=20) as client:
                    resp = await client.get(WEATHER_URL, params=params)
                    resp.raise_for_status()
                    payload = resp.json().get("daily", {})
                    last_err = None
                    break
            except Exception as e:
                last_err = e
                print(f"[Weather] attempt {attempt + 1} failed for ({lat},{lon}): {e}")
                if attempt < 2:
                    await asyncio.sleep(1)

        if last_err is not None:
            print(f"[Weather] all retries failed for ({lat},{lon}): {last_err}")
            return None

        times    = payload.get("time", [])
        precip   = payload.get("precipitation_sum", [])
        wind     = payload.get("wind_speed_10m_max", [])
        temp_max = payload.get("temperature_2m_max", [])
        temp_min = payload.get("temperature_2m_min", [])

        if not times or not precip:
            return None

        today_str = date.today().isoformat()
        try:
            today_idx = times.index(today_str)
        except ValueError:
            # If today is missing, assume the API returned past + future in order;
            # best guess: today is the first forecast entry after past_days.
            today_idx = min(14, len(times) - 1)

        def fnum(lst, idx):
            try:
                v = lst[idx]
                return float(v) if v is not None else 0.0
            except (IndexError, TypeError):
                return 0.0

        def fsum(lst, start, end):
            total = 0.0
            for i in range(max(0, start), min(len(lst), end)):
                v = lst[i]
                if v is None:
                    continue
                try:
                    total += float(v)
                except (ValueError, TypeError):
                    pass
            return total

        # Past windows exclude today so they match "rain that has fallen before now"
        rain_past_1d  = fsum(precip, today_idx - 1,  today_idx)
        rain_past_3d  = fsum(precip, today_idx - 3,  today_idx)
        rain_past_7d  = fsum(precip, today_idx - 7,  today_idx)
        rain_past_14d = fsum(precip, today_idx - 14, today_idx)

        # Future windows are the label horizon (matches rain_next_Nd at train time)
        rain_next_1d = fsum(precip, today_idx + 1, today_idx + 2)
        rain_next_3d = fsum(precip, today_idx + 1, today_idx + 4)

        result = {
            "temperature_2m_max": fnum(temp_max, today_idx),
            "temperature_2m_min": fnum(temp_min, today_idx),
            "wind_speed_10m_max": fnum(wind,     today_idx),
            "rain_past_1d":  rain_past_1d,
            "rain_past_3d":  rain_past_3d,
            "rain_past_7d":  rain_past_7d,
            "rain_past_14d": rain_past_14d,
            "rain_next_1d":  rain_next_1d,
            "rain_next_3d":  rain_next_3d,
        }
        _weather_cache[cache_key] = result
        return result

    # ── Threshold resolution ───────────────────────────────────────────────────

    @staticmethod
    def _resolve_typical_high(
        station: Dict,
        history_values: List[float],
        meta_high: Optional[float] = None,
    ) -> tuple:
        """
        Return (typical_high, source). Priority order:
          1. 'reported' – meta fetched directly from individual station endpoint
          2. 'reported' – from ea_api enrichment (usually None; stageScale is a URL)
          3. 'inferred' – 95th percentile of 30-day history
          4. 'default'  – current level × 1.6 (rainfall drives the prediction)
        """
        # Priority 1: individual station metadata fetch
        try:
            if meta_high is not None and float(meta_high) > 0:
                return float(meta_high), "reported"
        except (TypeError, ValueError):
            pass

        # Priority 2: enriched station dict (usually None from list endpoint)
        reported = (
            station.get("typical_range_high")
            or station.get("typicalRangeHigh")
        )
        try:
            if reported is not None and float(reported) > 0:
                return float(reported), "reported"
        except (TypeError, ValueError):
            pass

        if len(history_values) >= 5:
            arr = np.asarray(history_values, dtype=float)
            p95 = float(np.quantile(arr, 0.95))
            p50 = float(np.quantile(arr, 0.50))
            if p95 > 0 and (p95 - p50) > 0.02:
                return p95, "inferred"

        try:
            level = float(station.get("water_level") or 0.0)
        except (TypeError, ValueError):
            level = 0.0
        # Assume current level sits at roughly 60% of the bank — not a strong
        # claim, just enough to keep level-relative features in a plausible
        # range so the model's rainfall features dominate.
        default = max(level * 1.6, 1.0)
        return default, "default"

    # ── Feature assembly ──────────────────────────────────────────────────────

    def _build_features(
        self,
        station: Dict,
        weather: Dict,
        history: Dict[str, float],
        typical_high: float,
    ) -> Dict:
        try:
            level = float(station.get("water_level") or 0.0)
        except (TypeError, ValueError):
            level = 0.0

        lat = station.get("latitude", 0.0) or 0.0
        lon = station.get("longitude", 0.0) or 0.0
        today = date.today()

        sorted_dates = sorted(history.keys())                   # oldest → newest
        sorted_values = [history[d] for d in sorted_dates]

        def level_on(n: int) -> float:
            """Level n days ago. Fall back to nearest older value, then current."""
            target = (today - timedelta(days=n)).isoformat()
            if target in history:
                return history[target]
            # nearest date at or before target
            candidate = None
            for d in sorted_dates:
                if d <= target:
                    candidate = d
                else:
                    break
            if candidate is not None:
                return history[candidate]
            if sorted_values:
                return sorted_values[0]
            return level

        level_1d = level_on(1)
        level_2d = level_on(2)
        level_3d = level_on(3)
        level_4d = level_on(4)
        level_7d = level_on(7)

        # Rolling stats over the past 7 days (excluding today), matching training
        past_window = [history[d] for d in sorted_dates if d < today.isoformat()][-7:]
        if past_window:
            level_roll_7d     = float(np.mean(past_window))
            level_roll_max_7d = float(np.max(past_window))
        else:
            level_roll_7d     = level_1d
            level_roll_max_7d = level_1d

        lag1_above_threshold = 1 if level_1d > typical_high else 0

        return {
            "water_level":          level,
            "level_lag_1d":         level_1d,
            "level_lag_3d":         level_3d,
            "level_lag_7d":         level_7d,
            "level_change_1d":      level_1d - level_2d,
            "level_change_3d":      level_1d - level_4d,
            "level_roll_7d":        level_roll_7d,
            "level_roll_max_7d":    level_roll_max_7d,
            "level_pct_lag_1d":     level_1d / typical_high if typical_high > 0 else 0.0,
            "level_pct_lag_3d":     level_3d / typical_high if typical_high > 0 else 0.0,
            "lag1_above_threshold": lag1_above_threshold,
            # Rainfall — past + future forecast
            "rain_past_1d":         weather.get("rain_past_1d", 0.0),
            "rain_past_3d":         weather.get("rain_past_3d", 0.0),
            "rain_past_7d":         weather.get("rain_past_7d", 0.0),
            "rain_past_14d":        weather.get("rain_past_14d", 0.0),
            "rain_next_1d":         weather.get("rain_next_1d", 0.0),
            "rain_next_3d":         weather.get("rain_next_3d", 0.0),
            # Other weather
            "temperature_2m_max":   weather.get("temperature_2m_max", 12.0),
            "temperature_2m_min":   weather.get("temperature_2m_min", 6.0),
            "wind_speed_10m_max":   weather.get("wind_speed_10m_max", 5.0),
            # Calendar
            "month":                today.month,
            "day_of_year":          today.timetuple().tm_yday,
            # Location
            "latitude":             lat,
            "longitude":            lon,
        }

    # ── Sanity rule — cap probability when hydrology clearly says "no flood" ──

    def _apply_sanity_gate(
        self,
        prob: float,
        features: Dict,
        typical_high: float,
    ) -> float:
        """
        Even a well-trained model can spit out elevated scores when lag values
        are partly imputed. If the hydrological picture is clearly quiet —
        little past rain, little forecast rain, level well below threshold,
        no rising trend — force the probability back down.
        """
        level = features["water_level"]
        level_1d = features["level_lag_1d"]
        rain_past_3d = features["rain_past_3d"]
        rain_next_3d = features["rain_next_3d"]
        rising = features["level_change_1d"]

        pct = level / typical_high if typical_high > 0 else 0.0
        pct_lag = level_1d / typical_high if typical_high > 0 else 0.0

        quiet_rain = rain_past_3d < 5.0 and rain_next_3d < 5.0
        low_level = pct < 0.70 and pct_lag < 0.70
        not_rising = rising < 0.05   # under 5 cm/day rise

        if quiet_rain and low_level and not_rising:
            return min(prob, 0.10)

        mild_rain = rain_past_3d < 15.0 and rain_next_3d < 15.0
        modest_level = pct < 0.85 and pct_lag < 0.85
        if mild_rain and modest_level and not_rising:
            return min(prob, 0.30)

        return prob

    # ── Prediction ────────────────────────────────────────────────────────────

    async def predict(self, lat: float, lon: float, stations: List[Dict]) -> Dict:
        self._load()

        if not stations:
            # No EA stations nearby — fall back to a rainfall-only forecast so
            # the UI still shows something weather-aware rather than an empty
            # "no stations" result.
            weather = await self._fetch_weather(lat, lon)
            if weather is None:
                return {
                    "success":     True,
                    "risk_level":  "UNKNOWN",
                    "probability": 0.0,
                    "confidence":  "low",
                    "reason":      "No nearby stations and weather data unavailable.",
                    "top_station": "",
                    "station_predictions": [],
                }
            prob = _rainfall_only_probability(weather)
            risk_level, _ = self._classify_risk(
                prob,
                {"threshold_source": "default", "history_days": 0},
                weather,
            )
            reason = _build_reason(
                risk_level, weather,
                {"station_name": "your area"}, []
            )
            return {
                "success":            True,
                "risk_level":         risk_level,
                "probability":        round(prob, 3),
                "confidence":         "low",
                "reason":             reason,
                "top_station":        "",
                "decision_threshold": round(self._decision_threshold, 3),
                "station_predictions": [],
            }

        async with httpx.AsyncClient(timeout=15) as client:
            weather_task  = self._fetch_weather(lat, lon)
            history_tasks = [
                self._fetch_station_history(client, s.get("ea_station_id", ""))
                for s in stations
            ]
            meta_tasks = [
                self._fetch_station_meta(client, s.get("ea_station_id", ""))
                for s in stations
            ]
            gathered = await asyncio.gather(
                weather_task, *history_tasks, *meta_tasks
            )
            n        = len(stations)
            weather  = gathered[0]
            histories = gathered[1 : n + 1]
            metas     = gathered[n + 1 :]

        weather_available = weather is not None
        if weather is None:
            # Fall back to neutral weather so the model can still use water-level data
            weather = {
                "rain_past_1d": 0.0, "rain_past_3d": 0.0,
                "rain_past_7d": 0.0, "rain_past_14d": 0.0,
                "rain_next_1d": 0.0, "rain_next_3d": 0.0,
                "temperature_2m_max": 12.0, "temperature_2m_min": 6.0,
                "wind_speed_10m_max": 5.0,
            }

        results = []

        for station, history, meta in zip(stations, histories, metas):
            history_values = list(history.values())
            meta_high = meta[0] if meta else None
            typical_high, threshold_source = self._resolve_typical_high(
                station, history_values, meta_high=meta_high
            )

            features = self._build_features(station, weather, history, typical_high)
            row = np.array([[features.get(f, 0.0) for f in self._features]])

            raw_prob = float(self._model.predict_proba(row)[0][1])
            prob = self._apply_sanity_gate(raw_prob, features, typical_high)

            # When we don't really know the threshold, let rainfall drive the
            # signal — clamp the level-relative contribution by blending toward
            # a rainfall-only baseline.
            if threshold_source == "default":
                rain_baseline = _rainfall_only_probability(weather)
                prob = 0.4 * prob + 0.6 * rain_baseline

            results.append({
                "station_id":       station.get("ea_station_id", ""),
                "station_name":     station.get("station_name", "Station"),
                "probability":      round(prob, 3),
                "raw_probability":  round(raw_prob, 3),
                "flood_likely":     prob >= self._decision_threshold,
                "water_level":      station.get("water_level"),
                "typical_high":     round(typical_high, 3),
                "threshold_source": threshold_source,
                "history_days":     len(history),
            })

        results.sort(key=lambda x: x["probability"], reverse=True)
        top  = results[0]
        prob = top["probability"]

        risk_level, confidence = self._classify_risk(prob, top, weather)
        reason = _build_reason(risk_level, weather, top, results)

        if not weather_available:
            confidence = "low"
            reason += " (Weather forecast unavailable — rainfall data estimated.)"

        return {
            "success":             True,
            "risk_level":          risk_level,
            "probability":         round(prob, 3),
            "confidence":          confidence,
            "reason":              reason,
            "top_station":         top["station_name"],
            "decision_threshold":  round(self._decision_threshold, 3),
            "station_predictions": results[:5],
        }

    def _classify_risk(self, prob: float, top: Dict, weather: Dict) -> tuple:
        """Map calibrated probability to a human risk band using saved thresholds."""
        b = self._bands

        # Support both new absolute-cut format and the older multiplier format
        severe_cut   = b.get("severe",   self._decision_threshold * b.get("severe_mult",   3.25))
        high_cut     = b.get("high",     self._decision_threshold * b.get("high_mult",     2.40))
        moderate_cut = b.get("moderate", self._decision_threshold * b.get("moderate_mult", 1.10))
        minimal_cut  = b.get("minimal",  self._decision_threshold * b.get("minimal_mult",  0.45))

        source = top.get("threshold_source", "reported")
        history_days = top.get("history_days", 0)
        if source == "reported" and history_days >= 5:
            confidence = "high"
        elif source == "reported" or history_days >= 5:
            confidence = "medium"
        else:
            confidence = "low"

        if prob >= severe_cut:
            return "SEVERE", confidence
        if prob >= high_cut:
            return "HIGH", confidence
        if prob >= moderate_cut:
            return "MODERATE", confidence if confidence != "high" else "medium"
        if prob >= minimal_cut:
            return "MINIMAL", "low" if confidence == "low" else confidence
        return "NORMAL", confidence if confidence != "low" else "medium"


def _rainfall_only_probability(weather: Dict) -> float:
    """
    Rainfall-driven fallback score in [0, 1]. Used when we don't have a
    trustworthy water-level threshold so the model's level features can't be
    taken at face value. Calibrated roughly against the training set:
      <5mm      -> near 0
      ~15mm     -> ~0.2
      ~30mm     -> ~0.45
      ~60mm     -> ~0.75
      >=100mm   -> near 1
    """
    past_7 = max(weather.get("rain_past_7d", 0.0) or 0.0, 0.0)
    next_3 = max(weather.get("rain_next_3d", 0.0) or 0.0, 0.0)
    past_3 = max(weather.get("rain_past_3d", 0.0) or 0.0, 0.0)

    combined = 0.5 * past_7 + 1.0 * next_3 + 0.6 * past_3
    # Logistic-ish squash; 30mm combined -> ~0.5
    k = 0.045
    import math
    prob = 1.0 / (1.0 + math.exp(-k * (combined - 30.0)))
    return prob


def _describe_rain(past_3: float, past_7: float, next_3: float) -> str:
    """Short phrase that describes what the rainfall numbers mean."""
    if next_3 >= 40 or past_3 >= 40:
        return f"extreme rainfall ({past_3:.0f}mm in 72h, {next_3:.0f}mm forecast)"
    if next_3 >= 20 or past_3 >= 25:
        return f"sustained heavy rainfall ({past_3:.0f}mm recent, {next_3:.0f}mm forecast)"
    if next_3 >= 10 or past_3 >= 10:
        return f"moderate rainfall ({past_3:.0f}mm recent, {next_3:.0f}mm forecast)"
    if past_7 > 15:
        return f"persistent wet conditions ({past_7:.0f}mm over 7 days)"
    if past_3 > 1 or next_3 > 1:
        return f"minor rainfall ({past_3:.0f}mm recent, {next_3:.0f}mm forecast)"
    return "little to no rainfall"


def _describe_levels(top: Dict, results: List[Dict]) -> str:
    elevated = [
        r for r in results
        if r.get("water_level") is not None
        and r.get("typical_high", 0) > 0
        and r["water_level"] >= 0.75 * r["typical_high"]
    ]
    above = [
        r for r in elevated
        if r["water_level"] >= r.get("typical_high", 0)
    ]
    if above:
        names = ", ".join(r["station_name"] for r in above[:2])
        return f"water already above typical high at {names}"
    if len(elevated) >= 2:
        names = ", ".join(r["station_name"] for r in elevated[:2])
        return f"elevated water levels at {names}"
    if len(elevated) == 1:
        return f"elevated water level at {elevated[0]['station_name']}"
    return "water levels within normal range at all nearby stations"


def _build_reason(
    risk_level: str, weather: Dict, top: Dict, results: List[Dict]
) -> str:
    past_3 = weather.get("rain_past_3d", 0) or 0
    past_7 = weather.get("rain_past_7d", 0) or 0
    next_3 = weather.get("rain_next_3d", 0) or 0

    rain_phrase = _describe_rain(past_3, past_7, next_3)
    level_phrase = _describe_levels(top, results)
    station_name = top.get("station_name", "nearby station")

    if risk_level == "NORMAL":
        return (
            f"{rain_phrase.capitalize()}. {level_phrase.capitalize()}. "
            "No flood risk expected."
        )
    if risk_level == "MINIMAL":
        return (
            f"{rain_phrase.capitalize()}. {level_phrase.capitalize()}. "
            "Minor risk — monitor conditions."
        )
    if risk_level == "MODERATE":
        return (
            f"{level_phrase.capitalize()} following {rain_phrase}. "
            "Conditions could worsen if further rain occurs."
        )
    if risk_level == "HIGH":
        return (
            f"Flood risk: {rain_phrase} and rising water levels detected near "
            f"{station_name}. River expected to approach or exceed flood "
            "threshold within 24 hours."
        )
    if risk_level == "SEVERE":
        return (
            f"Severe flood risk: {rain_phrase} combined with saturated soil "
            f"and rising river levels at multiple nearby stations. "
            "Immediate action may be required — follow official guidance."
        )
    return f"{rain_phrase.capitalize()}. {level_phrase.capitalize()}."
