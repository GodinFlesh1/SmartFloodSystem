"""
Fetch all EA monitoring stations from the Hydrology API.
Also fetches typicalRangeHigh thresholds from the flood-monitoring API
using stationReference as the bridge between the two APIs.
Saves to: data/raw/stations.csv
"""

import requests
import pandas as pd
from pathlib import Path
from tqdm import tqdm

HYDROLOGY_BASE    = "https://environment.data.gov.uk/hydrology"
FLOOD_MON_BASE    = "https://environment.data.gov.uk/flood-monitoring"
OUT_PATH = Path(__file__).parent.parent / "data" / "raw" / "stations.csv"


def _get_level_measure_iri(measures: list) -> str:
    """
    Pick the best daily level measure IRI from a station's measures list.
    Priority: daily mean > daily max > instantaneous (15-min)
    """
    daily_mean = ""
    daily_max  = ""
    instant    = ""

    for m in measures:
        iri   = m.get("@id", "")
        param = m.get("parameter", "")
        if param != "level":
            continue
        period = m.get("period", 0)
        if period == 86400:
            stat = m.get("valueStatistic", {}).get("@id", "")
            if "mean" in stat:
                daily_mean = iri
            elif "maximum" in stat:
                daily_max = iri
        elif period == 900:
            instant = iri

    return daily_mean or daily_max or instant


def fetch_thresholds_by_reference(station_ref: str) -> dict:
    """
    Fetch typicalRangeLow / typicalRangeHigh from the flood-monitoring API
    using the stationReference (e.g. '51107').
    Returns dict with keys typical_low, typical_high (or None if not found).
    """
    url = f"{FLOOD_MON_BASE}/id/stations/{station_ref}"
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code != 200:
            return {"typical_low": None, "typical_high": None}
        data = resp.json().get("items", {})
        measures = data.get("measures", [])
        if isinstance(measures, dict):
            measures = [measures]
        for m in measures:
            if m.get("parameter") == "level":
                return {
                    "typical_low":  m.get("typicalRangeLow"),
                    "typical_high": m.get("typicalRangeHigh"),
                }
    except Exception:
        pass
    return {"typical_low": None, "typical_high": None}


def fetch_stations(max_stations: int = None) -> pd.DataFrame:
    print("Fetching stations from EA Hydrology API...")

    url    = f"{HYDROLOGY_BASE}/id/stations.json"
    params = {"observedProperty": "waterLevel", "_limit": 2000}

    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    items = resp.json().get("items", [])
    if max_stations:
        items = items[:max_stations]
    print(f"  Found {len(items)} stations")

    rows = []
    for s in tqdm(items, desc="Parsing stations"):
        station_uuid = s.get("notation", "") or s.get("@id", "").split("/")[-1]
        station_ref  = s.get("stationReference", "")

        measures = s.get("measures", [])
        if isinstance(measures, dict):
            measures = [measures]

        measure_iri = _get_level_measure_iri(measures)

        rows.append({
            "station_id":    station_uuid,    # UUID — used for hydrology readings
            "station_ref":   station_ref,     # EA reference — used for flood-monitoring
            "station_iri":   s.get("@id", ""),
            "measure_iri":   measure_iri,
            "station_name":  s.get("label", ""),
            "river_name":    s.get("riverName", ""),
            "town":          s.get("town", ""),
            "latitude":      s.get("lat"),
            "longitude":     s.get("long"),
            "typical_low":   None,            # filled in next step
            "typical_high":  None,
        })

    df = pd.DataFrame(rows)
    df = df.dropna(subset=["latitude", "longitude"])
    df = df[df["measure_iri"] != ""]          # must have a usable measure
    print(f"  {len(df)} stations have a level measure IRI")

    # Fetch flood thresholds via stationReference
    print("  Fetching flood thresholds from flood-monitoring API...")
    for idx, row in tqdm(df.iterrows(), total=len(df), desc="Thresholds"):
        if row["station_ref"]:
            t = fetch_thresholds_by_reference(row["station_ref"])
            df.at[idx, "typical_low"]  = t["typical_low"]
            df.at[idx, "typical_high"] = t["typical_high"]

    print(f"  Stations with threshold data: "
          f"{df['typical_high'].notna().sum()} / {len(df)}")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_PATH, index=False)
    print(f"  Saved → {OUT_PATH}")
    return df


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--max", type=int, default=None)
    args = parser.parse_args()
    fetch_stations(max_stations=args.max)
