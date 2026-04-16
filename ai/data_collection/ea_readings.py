"""
Fetch historical daily water level readings from the EA Hydrology API.

Correct endpoint (from official docs):
  GET /hydrology/id/measures/{measure_id}/readings
  Date params: mineq-date (start inclusive), max-date (end exclusive)

Saves per-station CSVs to: data/raw/readings/{station_id}.csv
Then merges all into:      data/raw/readings_all.csv
"""

import time
import requests
import pandas as pd
from pathlib import Path
from datetime import date, datetime, timedelta
from tqdm import tqdm

HYDROLOGY_BASE = "https://environment.data.gov.uk/hydrology"
STATIONS_CSV   = Path(__file__).parent.parent / "data" / "raw" / "stations.csv"
OUT_DIR        = Path(__file__).parent.parent / "data" / "raw" / "readings"
OUT_MERGED     = Path(__file__).parent.parent / "data" / "raw" / "readings_all.csv"

START_DATE = "2020-01-01"
END_DATE   = date.today().isoformat()
CHUNK_DAYS = 365   # 1-year chunks — daily measures are ~365 rows/year, well within limits
LIMIT      = 2000


def fetch_readings_for_station(station_id: str, measure_iri: str) -> pd.DataFrame:
    """
    Fetch all daily level readings for one station using its measure IRI.
    Endpoint: /hydrology/id/measures/{measure_id}/readings
    """
    # Extract just the measure ID from the full IRI
    # e.g. http://...hydrology/id/measures/48513a18-...-level-max-86400-m-qualified
    #   → 48513a18-...-level-max-86400-m-qualified
    measure_id = measure_iri.rstrip("/").split("/")[-1]

    url   = f"{HYDROLOGY_BASE}/id/measures/{measure_id}/readings.json"
    start = datetime.strptime(START_DATE, "%Y-%m-%d")
    end   = datetime.strptime(END_DATE,   "%Y-%m-%d")

    all_rows = []
    current  = start

    while current < end:
        chunk_end = min(current + timedelta(days=CHUNK_DAYS), end)

        params = {
            "mineq-date": current.strftime("%Y-%m-%d"),
            "max-date":   chunk_end.strftime("%Y-%m-%d"),
            "_limit":     LIMIT,
        }

        try:
            resp = requests.get(url, params=params, timeout=30)
            if resp.status_code == 404:
                # Measure IRI not valid for this station — skip entirely
                return pd.DataFrame()
            resp.raise_for_status()
            items = resp.json().get("items", [])
        except Exception as e:
            print(f"    [WARN] {station_id} chunk {current.date()}: {e}")
            current = chunk_end + timedelta(days=1)
            continue

        for item in items:
            # API always returns dateTime; some daily measures also have date
            dt_str  = item.get("dateTime") or item.get("date", "")
            value   = item.get("value")
            quality = item.get("quality", "Good")
            if not dt_str or value is None:
                continue
            if quality not in ("Good", "Estimated", "Unchecked"):
                continue
            try:
                all_rows.append({
                    "station_id":  station_id,
                    "date":        dt_str[:10],
                    "water_level": float(value),
                })
            except (ValueError, TypeError):
                pass

        current = chunk_end + timedelta(days=1)
        time.sleep(0.25)

    if not all_rows:
        return pd.DataFrame()

    df = pd.DataFrame(all_rows)
    df["date"] = pd.to_datetime(df["date"])

    # Always aggregate to daily — handles both sub-daily and daily readings
    df = (
        df.groupby(["station_id", "date"])["water_level"]
        .agg(["mean", "max", "min"])
        .reset_index()
        .rename(columns={
            "mean": "water_level",
            "max":  "water_level_max",
            "min":  "water_level_min",
        })
    )

    return df


def fetch_all_readings(max_stations: int = None):
    if not STATIONS_CSV.exists():
        raise FileNotFoundError(f"Run ea_stations.py first — {STATIONS_CSV} not found")

    stations = pd.read_csv(STATIONS_CSV)
    stations = stations.dropna(subset=["measure_iri"])
    stations = stations[stations["measure_iri"].str.strip() != ""]

    if max_stations:
        stations = stations.head(max_stations)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    all_frames = []
    skipped = 0

    for _, row in tqdm(stations.iterrows(), total=len(stations), desc="Fetching readings"):
        station_id  = str(row["station_id"])
        measure_iri = str(row["measure_iri"])
        out_file    = OUT_DIR / f"{station_id}.csv"

        # Resume: skip already-fetched stations
        if out_file.exists():
            df = pd.read_csv(out_file, parse_dates=["date"])
            if not df.empty:
                all_frames.append(df)
            continue

        df = fetch_readings_for_station(station_id, measure_iri)

        if df.empty:
            skipped += 1
            pd.DataFrame(columns=["station_id", "date", "water_level"]).to_csv(
                out_file, index=False
            )
            continue

        df.to_csv(out_file, index=False)
        all_frames.append(df)

    print(f"\nFetched {len(all_frames)} stations | Skipped (no data): {skipped}")

    empty_df = pd.DataFrame(columns=["station_id", "date", "water_level",
                                      "water_level_max", "water_level_min"])
    if all_frames:
        merged = pd.concat(all_frames, ignore_index=True)
        merged.to_csv(OUT_MERGED, index=False)
        print(f"Readings saved → {OUT_MERGED}  ({len(merged):,} rows)")
        return merged

    empty_df.to_csv(OUT_MERGED, index=False)
    print("[WARN] No readings found — empty file created")
    return empty_df


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--max", type=int, default=None)
    args = parser.parse_args()
    fetch_all_readings(max_stations=args.max)
