"""
Master data collection script. Run this once to build the full dataset.

Usage:
  python collect_all.py             # full collection (~1500 stations, takes ~30 min)
  python collect_all.py --max 50    # test run with 50 stations (~2 min)
"""

import argparse
from data_collection.ea_stations  import fetch_stations
from data_collection.ea_readings  import fetch_all_readings
from data_collection.weather      import fetch_all_weather
from data_collection.build_dataset import build_dataset


def main(max_stations: int = None):
    print("=" * 60)
    print("EcoFlood — Data Collection Pipeline")
    print("=" * 60)

    print("\n[1/4] Fetching EA station list...")
    stations = fetch_stations(max_stations=max_stations)
    print(f"      Done — {len(stations)} stations")

    print("\n[2/4] Fetching historical water level readings...")
    fetch_all_readings(max_stations=max_stations)
    print("      Done")

    print("\n[3/4] Fetching historical weather data...")
    fetch_all_weather(max_stations=max_stations)
    print("      Done")

    print("\n[4/4] Building labeled training dataset...")
    df = build_dataset()
    print(f"      Done — {len(df):,} training rows")

    print("\n" + "=" * 60)
    print("Data collection complete!")
    print("Next step: open ai/notebooks/ and train the model.")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--max", type=int, default=None,
        help="Max stations to process (omit for full run)"
    )
    args = parser.parse_args()
    main(max_stations=args.max)
