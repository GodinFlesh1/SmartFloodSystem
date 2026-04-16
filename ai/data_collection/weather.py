"""
Fetch historical daily weather using NASA POWER API.
- Free, no API key, no strict rate limits (built for bulk research use)
- Resolution: ~0.5 degree grid (MERRA-2)
- URL: https://power.larc.nasa.gov/api/temporal/daily/point

Column mapping (matches build_dataset.py + train.py expectations):
  PRECTOTCORR → precipitation_sum, rain_sum  (mm/day)
  T2M_MAX     → temperature_2m_max           (°C)
  T2M_MIN     → temperature_2m_min           (°C)
  WS10M_MAX   → wind_speed_10m_max           (m/s)
  precipitation_hours, et0_fao_evapotranspiration → None (XGBoost handles NaN)

Saves per-station CSVs to: data/raw/weather/
Merges all into:           data/raw/weather_all.csv
"""

import time
import requests
import pandas as pd
from pathlib import Path
from datetime import date, timedelta
from tqdm import tqdm

NASA_URL     = "https://power.larc.nasa.gov/api/temporal/daily/point"
STATIONS_CSV = Path(__file__).parent.parent / "data" / "raw" / "stations.csv"
OUT_DIR      = Path(__file__).parent.parent / "data" / "raw" / "weather2"
OUT_MERGED   = Path(__file__).parent.parent / "data" / "raw" / "weather2_all.csv"

START_DATE = "20200101"
END_DATE   = (date.today() - timedelta(days=1)).strftime("%Y%m%d")

COLS = [
    "station_id", "date",
    "precipitation_sum", "rain_sum", "precipitation_hours",
    "temperature_2m_max", "temperature_2m_min", "wind_speed_10m_max",
    "et0_fao_evapotranspiration",
]


def fetch_one(station_id: str, lat: float, lon: float) -> pd.DataFrame:
    params = {
        "parameters": "PRECTOTCORR,T2M_MAX,T2M_MIN,WS10M_MAX",
        "community":  "RE",
        "longitude":  round(lon, 4),
        "latitude":   round(lat, 4),
        "start":      START_DATE,
        "end":        END_DATE,
        "format":     "JSON",
    }

    for attempt in range(4):
        try:
            resp = requests.get(NASA_URL, params=params, timeout=60)
            if resp.status_code == 429:
                wait = 30 * (attempt + 1)
                print(f"\n  [429] {station_id} — waiting {wait}s")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            data = resp.json()
            break
        except Exception as e:
            if attempt == 3:
                print(f"\n  [WARN] {station_id}: {e}")
                return pd.DataFrame()
            time.sleep(5 * (attempt + 1))
    else:
        return pd.DataFrame()

    try:
        params_data = data["properties"]["parameter"]
    except (KeyError, TypeError):
        return pd.DataFrame()

    precip = params_data.get("PRECTOTCORR", {})
    t_max  = params_data.get("T2M_MAX",     {})
    t_min  = params_data.get("T2M_MIN",     {})
    ws_max = params_data.get("WS10M_MAX",   {})

    if not precip:
        return pd.DataFrame()

    def clean(v):
        """NASA POWER uses -999 as missing value."""
        return None if (v is None or v <= -990) else v

    rows = []
    for d, pval in precip.items():
        rows.append({
            "station_id":                 station_id,
            "date":                       f"{d[:4]}-{d[4:6]}-{d[6:]}",
            "precipitation_sum":          clean(pval),
            "rain_sum":                   clean(pval),
            "precipitation_hours":        None,
            "temperature_2m_max":         clean(t_max.get(d)),
            "temperature_2m_min":         clean(t_min.get(d)),
            "wind_speed_10m_max":         clean(ws_max.get(d)),
            "et0_fao_evapotranspiration": None,
        })

    return pd.DataFrame(rows) if rows else pd.DataFrame()


def fetch_all_weather(max_stations: int = None, delay: float = 0.5):
    if not STATIONS_CSV.exists():
        raise FileNotFoundError(f"Run ea_stations.py first — {STATIONS_CSV} not found")

    stations = pd.read_csv(STATIONS_CSV).dropna(subset=["latitude", "longitude"])
    if max_stations:
        stations = stations.head(max_stations)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    pending    = []
    all_frames = []

    for _, row in stations.iterrows():
        sid      = str(row["station_id"])
        out_file = OUT_DIR / f"{sid}.csv"
        if out_file.exists():
            df = pd.read_csv(out_file)
            if not df.empty:
                all_frames.append(df)
        else:
            pending.append((sid, row["latitude"], row["longitude"]))

    print(f"Cached : {len(all_frames)} stations")
    print(f"Pending: {len(pending)} stations")
    print(f"Delay  : {delay}s between requests")
    print(f"Source : NASA POWER API (no quota)\n")

    skipped = new_count = 0

    for sid, lat, lon in tqdm(pending, desc="Fetching weather"):
        df       = fetch_one(sid, lat, lon)
        out_file = OUT_DIR / f"{sid}.csv"

        if df.empty:
            skipped += 1
            pd.DataFrame(columns=COLS).to_csv(out_file, index=False)
        else:
            df.to_csv(out_file, index=False)
            all_frames.append(df)
            new_count += 1

        time.sleep(delay)

    print(f"\nFetched: {new_count} new | Skipped (no data): {skipped}")

    if all_frames:
        merged = pd.concat(all_frames, ignore_index=True)
        merged.to_csv(OUT_MERGED, index=False)
        print(f"Saved  → {OUT_MERGED}")
        print(f"Rows   : {len(merged):,}")
        return merged

    return pd.DataFrame()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--max",   type=int,   default=None, help="Limit stations")
    parser.add_argument("--delay", type=float, default=0.5,  help="Seconds between requests (default: 0.5)")
    args = parser.parse_args()
    fetch_all_weather(max_stations=args.max, delay=args.delay)
