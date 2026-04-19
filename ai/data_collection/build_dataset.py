"""
Merge station metadata + water level readings + weather data,
then engineer features and create flood labels.

Label logic:
  flood = 1  if water level exceeds typical_high any day in t+1..t+3
  flood = 0  otherwise

Features use only PAST water levels plus past AND forecasted rainfall —
matches what the predictor has access to at inference time.

Output: data/processed/flood_dataset.csv
"""

import pandas as pd
import numpy as np
from pathlib import Path

RAW_DIR       = Path(__file__).parent.parent / "data" / "raw"
PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"
OUT_FILE      = PROCESSED_DIR / "flood_dataset.csv"


def load_data():
    print("Loading raw data...")

    stations_path = RAW_DIR / "stations.csv"
    readings_path = RAW_DIR / "readings_all.csv"
    weather_path  = RAW_DIR / "weather_all.csv"

    for p in [stations_path, readings_path, weather_path]:
        if not p.exists():
            raise FileNotFoundError(
                f"Missing: {p}\n"
                f"Run collect_all.py first to generate all raw data files."
            )

    stations = pd.read_csv(stations_path)
    readings = pd.read_csv(readings_path, parse_dates=["date"])
    weather  = pd.read_csv(weather_path,  parse_dates=["date"])

    if readings.empty:
        raise ValueError(
            "readings_all.csv is empty — the EA API returned no readings.\n"
            "Check your internet connection or try again later."
        )

    print(f"  Stations : {len(stations):,}")
    print(f"  Readings : {len(readings):,}")
    print(f"  Weather  : {len(weather):,}")
    return stations, readings, weather


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Create lag/rolling features from past water level + past-and-future rainfall."""
    df = df.sort_values(["station_id", "date"]).copy()
    grp = df.groupby("station_id")

    # ── Water level — PAST lags only (never use future) ───────────────────────
    df["level_lag_1d"]    = grp["water_level"].shift(1)
    df["level_lag_3d"]    = grp["water_level"].shift(3)
    df["level_lag_7d"]    = grp["water_level"].shift(7)
    df["level_change_1d"] = df["level_lag_1d"] - grp["water_level"].shift(2)
    df["level_change_3d"] = df["level_lag_1d"] - grp["water_level"].shift(4)
    df["level_roll_7d"]   = grp["water_level"].transform(
        lambda x: x.shift(1).rolling(7, min_periods=1).mean()
    )
    df["level_roll_max_7d"] = grp["water_level"].transform(
        lambda x: x.shift(1).rolling(7, min_periods=1).max()
    )

    # ── Rainfall — past accumulation (what has fallen already) ────────────────
    df["rain_past_1d"]  = grp["precipitation_sum"].shift(0)   # today's reported rain
    df["rain_past_3d"]  = grp["precipitation_sum"].transform(
        lambda x: x.rolling(3, min_periods=1).sum()
    )
    df["rain_past_7d"]  = grp["precipitation_sum"].transform(
        lambda x: x.rolling(7, min_periods=1).sum()
    )
    df["rain_past_14d"] = grp["precipitation_sum"].transform(
        lambda x: x.rolling(14, min_periods=1).sum()
    )

    # ── Rainfall — FUTURE forecast (label window) ─────────────────────────────
    # At inference we fetch these from Open-Meteo forecast_days. Using future
    # data here is NOT leakage w.r.t. the label: it's legitimately available as
    # a weather forecast when predicting t+1..t+3 floods.
    future_rain_1 = grp["precipitation_sum"].shift(-1)
    future_rain_2 = grp["precipitation_sum"].shift(-2)
    future_rain_3 = grp["precipitation_sum"].shift(-3)
    df["rain_next_1d"] = future_rain_1.fillna(0.0)
    df["rain_next_3d"] = (
        future_rain_1.fillna(0.0)
        + future_rain_2.fillna(0.0)
        + future_rain_3.fillna(0.0)
    )

    # ── Calendar ──────────────────────────────────────────────────────────────
    df["month"]       = df["date"].dt.month
    df["day_of_year"] = df["date"].dt.dayofyear

    # ── Level relative to station thresholds — past-only ──────────────────────
    # level_pct_lag_1d = yesterday's level / threshold (past, not future)
    df["level_pct_lag_1d"] = np.where(
        df["typical_high"] > 0,
        df["level_lag_1d"] / df["typical_high"],
        np.nan,
    )
    df["level_pct_lag_3d"] = np.where(
        df["typical_high"] > 0,
        df["level_lag_3d"] / df["typical_high"],
        np.nan,
    )
    # Was water already above threshold yesterday? Strong but legitimate signal.
    df["lag1_above_threshold"] = (df["level_lag_1d"] > df["typical_high"]).astype(int)

    # Kept for severity calc, not used as a feature
    df["level_pct_of_typical_high"] = np.where(
        df["typical_high"] > 0,
        df["water_level"] / df["typical_high"],
        np.nan,
    )

    return df


def create_labels(df: pd.DataFrame) -> pd.DataFrame:
    """
    Forward-looking flood labels — predict floods BEFORE they happen.

    flood_in_1d : will water exceed threshold tomorrow?
    flood_in_3d : will water exceed threshold within 3 days?  ← primary label
    flood_in_7d : will water exceed threshold within 7 days?
    """
    df = df.sort_values(["station_id", "date"]).copy()
    grp = df.groupby("station_id")

    currently_flooding = (df["water_level"] > df["typical_high"])

    df["flood_in_1d"] = grp["water_level"].shift(-1).gt(df["typical_high"]).astype(int)
    df["flood_in_3d"] = (
        pd.concat([grp["water_level"].shift(-i) for i in range(1, 4)], axis=1)
        .gt(df["typical_high"].values.reshape(-1, 1))
        .any(axis=1)
        .astype(int)
    )
    df["flood_in_7d"] = (
        pd.concat([grp["water_level"].shift(-i) for i in range(1, 8)], axis=1)
        .gt(df["typical_high"].values.reshape(-1, 1))
        .any(axis=1)
        .astype(int)
    )

    df["flood"] = df["flood_in_3d"]

    pct = df["level_pct_of_typical_high"]
    conditions = [
        ~currently_flooding,
        currently_flooding & (pct < 1.1),
        currently_flooding & (pct < 1.25),
        pct >= 1.25,
    ]
    df["severity"] = np.select(conditions, [0, 1, 2, 3], default=0)

    return df


def build_dataset():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    stations, readings, weather = load_data()

    print("\nMerging readings with station thresholds...")
    df = readings.merge(
        stations[["station_id", "typical_low", "typical_high",
                  "latitude", "longitude", "river_name", "town"]],
        on="station_id",
        how="left",
    )

    before = len(df)
    df = df.dropna(subset=["water_level"])
    print(f"  Dropped {before - len(df):,} rows with missing water level")

    # Only fill thresholds for stations with enough history and plausible values.
    # Use the 97th percentile as a tighter flood proxy than 95th to cut false labels.
    missing_threshold = df["typical_high"].isna()
    if missing_threshold.any():
        print(f"  Imputing thresholds from history for "
              f"{df.loc[missing_threshold, 'station_id'].nunique()} stations...")
        counts = df.groupby("station_id")["water_level"].transform("count")
        p97 = df.groupby("station_id")["water_level"].transform(lambda x: x.quantile(0.97))
        p03 = df.groupby("station_id")["water_level"].transform(lambda x: x.quantile(0.03))

        # Only impute where we have at least 180 days of history and a spread
        spread = df.groupby("station_id")["water_level"].transform(lambda x: x.quantile(0.97) - x.quantile(0.50))
        fillable = missing_threshold & (counts >= 180) & (spread > 0.05)
        df.loc[fillable, "typical_high"] = p97[fillable]
        df.loc[fillable, "typical_low"]  = p03[fillable]

        # Drop stations that still have no threshold (not enough history) —
        # we cannot reliably label them
        before = len(df)
        df = df.dropna(subset=["typical_high"])
        df = df[df["typical_high"] > 0]
        print(f"  Dropped {before - len(df):,} rows without usable threshold")

    print("Merging weather data...")
    weather["date"] = pd.to_datetime(weather["date"])
    df = df.merge(weather, on=["station_id", "date"], how="left")

    # Fill missing rain with 0 so rolling/future sums work; weather is not
    # perfectly complete for every station-day.
    df["precipitation_sum"] = df["precipitation_sum"].fillna(0.0)

    print("Engineering features...")
    df = engineer_features(df)

    print("Creating flood labels...")
    df = create_labels(df)

    # Drop rows where key past features are unknown (first 7 days of station history)
    required = [
        "water_level", "level_lag_1d", "level_lag_3d",
        "level_change_1d", "level_roll_7d",
        "rain_past_3d", "rain_past_7d", "typical_high",
    ]
    df = df.dropna(subset=required)

    flood_pct = df["flood"].mean() * 100
    print(f"\nDataset summary:")
    print(f"  Total rows  : {len(df):,}")
    print(f"  Stations    : {df['station_id'].nunique():,}")
    print(f"  Date range  : {df['date'].min().date()} -> {df['date'].max().date()}")
    print(f"  Flood events: {df['flood'].sum():,} ({flood_pct:.1f}% of days)")

    df.to_csv(OUT_FILE, index=False)
    print(f"\nDataset saved → {OUT_FILE}")
    return df


if __name__ == "__main__":
    build_dataset()
