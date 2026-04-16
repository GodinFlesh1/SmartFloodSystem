"""
notification_service.py
-----------------------
Sends FCM push notifications to users when flood risk is HIGH or SEVERE
near their registered home location.

The scheduler calls `check_and_notify_all_users()` every 5 minutes.
"""

import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import firebase_admin
from firebase_admin import credentials, messaging

logger = logging.getLogger(__name__)

# ── Firebase Admin SDK init ────────────────────────────────────────────────────

_firebase_initialized = False


def _init_firebase():
    global _firebase_initialized
    if _firebase_initialized:
        return
    key_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH")
    if not key_path or not os.path.exists(key_path):
        logger.warning(
            "FIREBASE_SERVICE_ACCOUNT_PATH not set or file missing — "
            "push notifications will be disabled."
        )
        return
    cred = credentials.Certificate(key_path)
    firebase_admin.initialize_app(cred)
    _firebase_initialized = True
    logger.info("Firebase Admin SDK initialised.")


# ── Risk level ordering ────────────────────────────────────────────────────────

_RISK_ORDER = {"NO_SENSOR": 0, "NORMAL": 1, "ELEVATED": 2, "HIGH": 3, "SEVERE": 4}
_ALERT_THRESHOLD = {"HIGH", "SEVERE"}   # only notify at these levels

_ALERT_TITLES = {
    "HIGH":   "Flood Risk Alert",
    "SEVERE": "SEVERE Flood Warning",
}
_ALERT_BODIES = {
    "HIGH":   "{station} near you has HIGH flood risk. Stay alert and avoid waterways.",
    "SEVERE": "SEVERE flood warning at {station} near your area. Take immediate action.",
}


def _worst_station(stations: list) -> Optional[dict]:
    """Return the station with the highest risk level, or None if all are NORMAL/NO_SENSOR."""
    candidates = [s for s in stations if s.get("risk_level") in _ALERT_THRESHOLD]
    if not candidates:
        return None
    return max(candidates, key=lambda s: _RISK_ORDER.get(s.get("risk_level", "NORMAL"), 0))


# ── Send helpers ───────────────────────────────────────────────────────────────

def send_fcm_to_token(token: str, title: str, body: str, data: dict = None) -> bool:
    """Send a single FCM notification. Returns True on success."""
    if not _firebase_initialized:
        logger.debug("Firebase not initialised — skipping FCM send.")
        return False
    try:
        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            data=data or {},
            android=messaging.AndroidConfig(
                priority="high",
                notification=messaging.AndroidNotification(
                    channel_id="flood_alerts",
                    priority="max",
                    default_vibrate_timings=True,
                ),
            ),
            token=token,
        )
        messaging.send(message)
        return True
    except Exception as e:
        logger.error("FCM send error for token %s…: %s", token[:12], e)
        return False


def send_fcm_multicast(tokens: list[str], title: str, body: str, data: dict = None) -> int:
    """
    Send a notification to up to 500 tokens in one multicast call.
    Returns the number of successful sends.
    """
    if not _firebase_initialized or not tokens:
        return 0
    try:
        message = messaging.MulticastMessage(
            notification=messaging.Notification(title=title, body=body),
            data=data or {},
            android=messaging.AndroidConfig(
                priority="high",
                notification=messaging.AndroidNotification(
                    channel_id="flood_alerts",
                    priority="max",
                    default_vibrate_timings=True,
                ),
            ),
            tokens=tokens,
        )
        response = messaging.send_each_for_multicast(message)
        logger.info(
            "Multicast sent to %d tokens: %d success, %d failure",
            len(tokens),
            response.success_count,
            response.failure_count,
        )
        return response.success_count
    except Exception as e:
        logger.error("FCM multicast error: %s", e)
        return 0


# ── Core alert job ─────────────────────────────────────────────────────────────

async def check_and_notify_all_users():
    """
    Called by APScheduler every 5 minutes.
    For each user with notifications enabled + an FCM token + a home location,
    check nearby stations and send a push if risk is HIGH or SEVERE.
    A cooldown of 1 hour per user prevents spam during sustained flood events.
    """
    from app.database.db import get_users_for_notifications, mark_user_alerted
    from app.services.ea_api import EnvironmentAgencyService

    _init_firebase()

    ea_service = EnvironmentAgencyService()
    users = await get_users_for_notifications()

    if not users:
        logger.debug("No eligible users for notification check.")
        return

    logger.info("Notification check: %d eligible users.", len(users))
    now = datetime.now(timezone.utc)

    for user in users:
        try:
            home = user.get("home_location")
            if not home:
                continue

            lat = home.get("lat") or home.get("latitude")
            lon = home.get("lon") or home.get("longitude")
            if lat is None or lon is None:
                continue

            # Cooldown: skip if alerted within the last hour
            last_sent = user.get("last_alert_sent_at")
            if last_sent:
                last_sent_dt = datetime.fromisoformat(
                    last_sent.replace("Z", "+00:00")
                )
                if now - last_sent_dt < timedelta(hours=1):
                    continue

            # Fetch live risk data
            result = await ea_service.get_nearby_stations_live(lat, lon, dist_km=10)
            if not result.get("success"):
                continue

            worst = _worst_station(result.get("stations", []))
            if worst is None:
                continue

            risk_level = worst["risk_level"]
            station_name = worst.get("station_name", "a nearby station")
            title = _ALERT_TITLES[risk_level]
            body = _ALERT_BODIES[risk_level].format(station=station_name)

            token = user.get("fcm_token")
            if token:
                success = send_fcm_to_token(
                    token,
                    title,
                    body,
                    data={"risk_level": risk_level, "station_id": worst.get("ea_station_id", "")},
                )
                if success:
                    await mark_user_alerted(user["id"])
                    logger.info(
                        "Alert sent to user %s (%s at %s)",
                        user["id"],
                        risk_level,
                        station_name,
                    )

        except Exception as e:
            logger.error("Error processing user %s: %s", user.get("id"), e)
