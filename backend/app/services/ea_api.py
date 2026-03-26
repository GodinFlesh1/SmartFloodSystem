import httpx
from typing import List, Dict, Optional

class EnvironmentAgencyService:
    BASE_URL = "https://environment.data.gov.uk/flood-monitoring"

    async def get_all_stations(self, limit: int = 50) -> Dict:
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    f"{self.BASE_URL}/id/stations",
                    params={"_limit": limit}
                )
                if response.status_code == 200:
                    items = response.json().get('items', [])
                    return {"success": True, "total_stations": len(items), "stations": items}
                return {"success": False, "error": f"API status {response.status_code}"}
            except Exception as e:
                return {"success": False, "error": str(e)}

    async def get_nearby_stations_live(self, lat: float, lon: float, dist_km: float = 10) -> Dict:
        """
        Fetch stations near a lat/lon directly from EA API, enriched with latest readings.
        Reads are extracted from the measures embedded in each station response — this is
        reliable because it queries by station ID rather than a geographic readings search.
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # 1) Fetch stations with full measure details embedded
                stations_resp = await client.get(
                    f"{self.BASE_URL}/id/stations",
                    params={"lat": lat, "long": lon, "dist": dist_km, "_limit": 50}
                )
                if stations_resp.status_code != 200:
                    return {"success": False, "error": f"Stations API error {stations_resp.status_code}"}

                stations_raw = stations_resp.json().get('items', [])

                # 2) For each station fetch its latest readings by station ID —
                #    more reliable than a geographic bulk readings search.
                import asyncio

                async def fetch_readings(session: httpx.AsyncClient, ea_id: str) -> Dict[str, float]:
                    try:
                        r = await session.get(
                            f"{self.BASE_URL}/id/stations/{ea_id}/readings",
                            params={"latest": "true"},
                            timeout=10.0
                        )
                        if r.status_code != 200:
                            return {}
                        result: Dict[str, float] = {}
                        for item in r.json().get('items', []):
                            measure_uri = item.get('measure', '')
                            parts = measure_uri.split('/')[-1].split('-')
                            param = parts[1] if len(parts) > 1 else ''
                            val = item.get('value')
                            if param and val is not None and param not in result:
                                result[param] = val
                        return result
                    except Exception:
                        return {}

                # Build the list of (station, ea_id) pairs first
                station_ids = []
                for s in stations_raw:
                    raw_id = s.get('@id', '')
                    ea_id = raw_id.split('/stations/')[-1] if '/stations/' in raw_id else s.get('stationReference', '')
                    station_ids.append(ea_id)

                # Fetch all readings concurrently
                readings_list = await asyncio.gather(
                    *[fetch_readings(client, ea_id) for ea_id in station_ids]
                )
                readings_by_id = dict(zip(station_ids, readings_list))

                enriched = []
                for s, ea_id in zip(stations_raw, station_ids):
                    lat_s = s.get('lat')
                    lon_s = s.get('long')

                    dist = None
                    if lat_s and lon_s:
                        dist = round(_haversine(lat, lon, lat_s, lon_s), 2)

                    station_readings = readings_by_id.get(ea_id, {})
                    water_level = station_readings.get('level')
                    flow = station_readings.get('flow')
                    rainfall = station_readings.get('rainfall')
                    groundwater = station_readings.get('groundWater')
                    tidal = station_readings.get('tidal')

                    stage_scale = s.get('stageScale') or {}
                    if isinstance(stage_scale, str):
                        stage_scale = {}
                    typical_high = stage_scale.get('typicalRangeHigh')
                    typical_low = stage_scale.get('typicalRangeLow')

                    risk_level = _snapshot_risk(water_level, typical_high, typical_low)

                    enriched.append({
                        'ea_station_id': ea_id,
                        'station_name': s.get('label', 'Unknown'),
                        'latitude': lat_s,
                        'longitude': lon_s,
                        'town': s.get('town'),
                        'river_name': s.get('riverName'),
                        'typical_range_high': typical_high,
                        'typical_range_low': typical_low,
                        'water_level': water_level,
                        'flow': flow,
                        'rainfall': rainfall,
                        'groundwater': groundwater,
                        'tidal': tidal,
                        'distance_km': dist,
                        'risk_level': risk_level,
                    })

                enriched.sort(key=lambda x: x['distance_km'] or 9999)
                return {"success": True, "stations": enriched, "count": len(enriched)}

            except Exception as e:
                return {"success": False, "error": str(e)}

    async def get_station_latest_all_measures(self, station_id: str) -> Dict:
        """
        Fetch the latest reading for every measure at a station.
        Returns one value per measure type (level, flow, groundWater, rainfall, etc.)
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # Get station metadata (includes measure list and stage scale)
                meta_resp = await client.get(
                    f"{self.BASE_URL}/id/stations/{station_id}"
                )
                station_meta = {}
                if meta_resp.status_code == 200:
                    station_meta = meta_resp.json().get('items', {})
                    if isinstance(station_meta, list):
                        station_meta = station_meta[0] if station_meta else {}

                # Get latest readings for all measures
                readings_resp = await client.get(
                    f"{self.BASE_URL}/id/stations/{station_id}/readings",
                    params={"latest": "true"}
                )
                if readings_resp.status_code != 200:
                    return {"success": False, "error": f"API status {readings_resp.status_code}"}

                raw_items = readings_resp.json().get('items', [])

                measures = []
                seen = set()
                for item in raw_items:
                    measure_uri = item.get('measure', '')
                    if measure_uri in seen:
                        continue
                    seen.add(measure_uri)

                    # Parse parameter + qualifier from URI
                    # e.g. .../measures/3400TH-level-stage-i-15_min-mASD
                    label_parts = measure_uri.split('/')[-1].split('-') if measure_uri else []
                    parameter = label_parts[1] if len(label_parts) > 1 else 'unknown'
                    qualifier = label_parts[2] if len(label_parts) > 2 else ''
                    unit_name = label_parts[-1] if label_parts else ''

                    measures.append({
                        'parameter': parameter,
                        'qualifier': qualifier,
                        'unit': unit_name,
                        'value': item.get('value'),
                        'date_time': item.get('dateTime'),
                        'measure_uri': measure_uri,
                    })

                stage_scale = station_meta.get('stageScale') or {}
                if isinstance(stage_scale, str):
                    stage_scale = {}
                typical_high = stage_scale.get('typicalRangeHigh')
                typical_low = stage_scale.get('typicalRangeLow')

                # Find the water level reading to compute plain-English status
                water_level = next(
                    (m['value'] for m in measures if m['parameter'] == 'level'), None
                )
                status = _snapshot_risk(water_level, typical_high, typical_low)

                return {
                    "success": True,
                    "station_id": station_id,
                    "station_name": station_meta.get('label', ''),
                    "river_name": station_meta.get('riverName', ''),
                    "town": station_meta.get('town', ''),
                    "typical_range_low": typical_low,
                    "typical_range_high": typical_high,
                    "status": status,
                    "measures": measures,
                }
            except Exception as e:
                return {"success": False, "error": str(e)}

    async def get_station_readings(self, station_id: str, limit: int = 10) -> Dict:
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    f"{self.BASE_URL}/id/stations/{station_id}/readings",
                    params={"_sorted": "true", "_limit": limit}
                )
                if response.status_code == 200:
                    items = response.json().get('items', [])
                    return {"success": True, "station_id": station_id, "readings_count": len(items), "readings": items}
                return {"success": False, "error": f"API status {response.status_code}"}
            except Exception as e:
                return {"success": False, "error": str(e)}

    async def fetch_and_store_readings(self, ea_station_id: str) -> Dict:
        from app.database.db import get_station_by_ea_id, store_reading
        station = await get_station_by_ea_id(ea_station_id)
        if not station:
            return {"success": False, "error": "Station not found in DB. Sync stations first."}
        readings_result = await self.get_station_readings(ea_station_id, limit=10)
        if not readings_result.get('success'):
            return readings_result
        stored_count = 0
        for reading in readings_result.get('readings', []):
            try:
                stored = await store_reading(
                    station_id=station['id'],
                    ea_station_id=ea_station_id,
                    reading_data=reading
                )
                if stored:
                    stored_count += 1
            except Exception as e:
                print(f"Error storing reading: {e}")
        return {
            "success": True,
            "station_id": ea_station_id,
            "station_name": station['station_name'],
            "fetched": len(readings_result.get('readings', [])),
            "stored": stored_count
        }


def _haversine(lat1, lon1, lat2, lon2):
    from math import radians, cos, sin, asin, sqrt
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    return 6371 * 2 * asin(sqrt(a))


def _snapshot_risk(level: Optional[float], high: Optional[float], low: Optional[float]) -> str:
    """
    Plain-English risk label based on water level vs typical range.
      NO_SENSOR  – station has no recent reading
      NORMAL     – water is within the typical range
      ELEVATED   – water is approaching the top of the typical range
      HIGH       – water has exceeded the typical high
      SEVERE     – water is significantly above the typical high (flash flood risk)
    """
    if level is None:
        return "NO_SENSOR"
    if high is None:
        # No typical range on record — we have a reading but can't compare
        return "NORMAL"
    if level >= high * 1.3:
        return "SEVERE"
    if level >= high:
        return "HIGH"
    if level >= high * 0.75:
        return "ELEVATED"
    return "NORMAL"
