"""Quick diagnosis — tests 5 stations and shows exactly what's failing."""
import requests
import pandas as pd
from datetime import date, timedelta

stations = pd.read_csv('data/raw/stations.csv').dropna(subset=['latitude','longitude'])
already_fetched = set()
import os
weather_dir = 'data/raw/weather'
if os.path.exists(weather_dir):
    already_fetched = {f.replace('.csv','') for f in os.listdir(weather_dir)}

# Pick 5 stations that were NOT fetched
missing = stations[~stations['station_id'].astype(str).isin(already_fetched)].head(5)
END_DATE = (date.today() - timedelta(days=5)).isoformat()

VARS = [
    "precipitation_sum",
    "rain_sum",
    "precipitation_hours",
    "wind_speed_10m_max",
    "temperature_2m_max",
    "temperature_2m_min",
    "et0_fao_evapotranspiration",
]

for _, row in missing.iterrows():
    sid = str(row['station_id'])
    resp = requests.get('https://archive-api.open-meteo.com/v1/archive', params={
        'latitude':   round(row['latitude'], 4),
        'longitude':  round(row['longitude'], 4),
        'start_date': '2020-01-01',
        'end_date':   END_DATE,
        'daily':      ','.join(VARS),
        'timezone':   'Europe/London',
    }, timeout=30)
    data = resp.json()
    daily = data.get('daily', {})
    has_time = 'time' in daily
    rows = len(daily.get('time', []))
    error = data.get('reason', data.get('error', ''))
    print(f"{sid[:8]}  status={resp.status_code}  has_time={has_time}  rows={rows}  error={error!r}")
