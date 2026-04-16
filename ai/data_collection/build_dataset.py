"""
Merge station metadata + water level readings + weather data,
then engineer features and create flood labels.

Label logic:
  flood = 1  if water_level > typical_high threshold for that station
  flood = 0  otherwise

Output: data/processed/flood_dataset.csv  ← ready for model training
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
    """Create rolling and lag features from water level + rainfall."""
    df = df.sort_values(["station_id", "date"]).copy()

    grp = df.groupby("station_id")

    # ── Water level features ──────────────────────────────────────────────────
    df["level_lag_1d"]    = grp["water_level"].shift(1)
    df["level_lag_3d"]    = grp["water_level"].shift(3)
    df["level_lag_7d"]    = grp["water_level"].shift(7)
    df["level_change_1d"] = df["water_level"] - df["level_lag_1d"]   # rising/falling
    df["level_change_3d"] = df["water_level"] - df["level_lag_3d"]
    df["level_roll_7d"]   = grp["water_level"].transform(
        lambda x: x.rolling(7, min_periods=1).mean()
    )

    # ── Rainfall features ─────────────────────────────────────────────────────
    df["rain_3d"]  = grp["precipitation_sum"].transform(
        lambda x: x.rolling(3, min_periods=1).sum()
    )
    df["rain_7d"]  = grp["precipitation_sum"].transform(
        lambda x: x.rolling(7, min_periods=1).sum()
    )
    df["rain_14d"] = grp["precipitation_sum"].transform(
        lambda x: x.rolling(14, min_periods=1).sum()
    )
    df["rain_lag_1d"] = grp["precipitation_sum"].shift(1)

    # ── Calendar features ─────────────────────────────────────────────────────
    df["month"]       = df["date"].dt.month
    df["day_of_year"] = df["date"].dt.dayofyear
    # UK flood season: Oct–Mar = 1
    df["flood_season"] = df["month"].isin([10, 11, 12, 1, 2, 3]).astype(int)

    # ── Level relative to station thresholds ──────────────────────────────────
    df["level_above_typical_high"] = (
        df["water_level"] - df["typical_high"]
    ).clip(lower=0)

    # Yesterday's level ratio — not leaky (past data), but highly predictive
    df["level_pct_lag_1d"] = np.where(
        df["typical_high"] > 0,
        grp["water_level"].shift(1) / df["typical_high"],
        np.nan,
    )
    df["level_pct_lag_3d"] = np.where(
        df["typical_high"] > 0,
        grp["water_level"].shift(3) / df["typical_high"],
        np.nan,
    )

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

    This removes data leakage: the model must predict future state
    from current/past observations only.
    """
    df = df.sort_values(["station_id", "date"]).copy()
    grp = df.groupby("station_id")

    # Current flood state (for reference, NOT used as training label)
    currently_flooding = (df["water_level"] > df["typical_high"])

    # Forward-shifted flood flags
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

    # Primary training label = flood within 3 days
    df["flood"] = df["flood_in_3d"]

    # Severity based on current level relative to threshold (for reference)
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

    # Merge readings with station thresholds
    print("\nMerging readings with station thresholds...")
    df = readings.merge(
        stations[["station_id", "typical_low", "typical_high",
                  "latitude", "longitude", "river_name", "town"]],
        on="station_id",
        how="left",
    )

    # Drop rows with no water level
    before = len(df)
    df = df.dropna(subset=["water_level"])
    print(f"  Dropped {before - len(df):,} rows with missing water level")

    # Fill missing thresholds using per-station percentiles from historical data
    # 95th percentile = proxy for flood threshold (level exceeded only 5% of the time)
    missing_threshold = df["typical_high"].isna()
    if missing_threshold.any():
        print(f"  Computing thresholds from historical data for "
              f"{df.loc[missing_threshold, 'station_id'].nunique()} stations...")
        p95 = df.groupby("station_id")["water_level"].transform(lambda x: x.quantile(0.95))
        p05 = df.groupby("station_id")["water_level"].transform(lambda x: x.quantile(0.05))
        df.loc[missing_threshold, "typical_high"] = p95[missing_threshold]
        df.loc[missing_threshold, "typical_low"]  = p05[missing_threshold]
    print(f"  All stations have threshold data: {df['typical_high'].notna().all()}")

    # Merge weather
    print("Merging weather data...")
    weather["date"] = pd.to_datetime(weather["date"])
    df = df.merge(weather, on=["station_id", "date"], how="left")

    # Feature engineering
    print("Engineering features...")
    df = engineer_features(df)

    # Create labels
    print("Creating flood labels...")
    df = create_labels(df)

    # Drop rows still missing key features
    feature_cols = [
        "water_level", "level_lag_1d", "level_change_1d",
        "rain_3d", "rain_7d", "typical_high",
    ]
    df = df.dropna(subset=feature_cols)

    # Summary
    flood_pct = df["flood"].mean() * 100
    print(f"\nDataset summary:")
    print(f"  Total rows  : {len(df):,}")
    print(f"  Stations    : {df['station_id'].nunique():,}")
    print(f"  Date range  : {df['date'].min().date()} → {df['date'].max().date()}")
    print(f"  Flood events: {df['flood'].sum():,} ({flood_pct:.1f}% of days)")
    print(f"\nSeverity breakdown:")
    print(df["severity"].value_counts().sort_index().rename({
        0: "MINIMAL", 1: "MODERATE", 2: "HIGH", 3: "SEVERE"
    }))

    df.to_csv(OUT_FILE, index=False)
    print(f"\nDataset saved → {OUT_FILE}")
    return df


if __name__ == "__main__":
    build_dataset()
