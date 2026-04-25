import os
from typing import Optional
import firebase_admin
from firebase_admin import credentials, auth as firebase_auth
from fastapi import Header, HTTPException, Depends


def init_firebase():
    if not firebase_admin._apps:
        cred = credentials.Certificate({
            "type": "service_account",
            "project_id": os.getenv("FIREBASE_PROJECT_ID"),
            "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID"),
            "private_key": os.getenv("FIREBASE_PRIVATE_KEY", "").replace("\\n", "\n"),
            "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
            "client_id": os.getenv("FIREBASE_CLIENT_ID"),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": os.getenv("FIREBASE_CLIENT_CERT_URL"),
        })
        firebase_admin.initialize_app(cred)


async def _verify_jwt(authorization: str) -> dict:
    """Verify Firebase Bearer token and return the decoded claims."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = authorization[7:]
    try:
        return firebase_auth.verify_id_token(token)
    except firebase_auth.ExpiredIdTokenError:
        raise HTTPException(status_code=401, detail="Token expired")
    except firebase_auth.InvalidIdTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception:
        raise HTTPException(status_code=401, detail="Authentication failed")


async def verify_token(
    authorization: str = Header(...),
    x_device_id: Optional[str] = Header(None, alias="X-Device-ID"),
) -> dict:
    """
    Verify JWT + device binding.
    If X-Device-ID is sent and a different device is already registered
    for this UID, the request is rejected with 403.
    First-time requests (no device stored yet) are allowed through.
    """
    from app.database.db import get_device_id_for_user

    user = await _verify_jwt(authorization)

    if x_device_id:
        stored = await get_device_id_for_user(user["uid"])
        if stored is not None and stored != x_device_id:
            raise HTTPException(
                status_code=403,
                detail="This account is registered to another device",
            )

    return user


async def verify_token_no_device(authorization: str = Header(...)) -> dict:
    """
    JWT-only check with no device binding.
    Used for the register-device endpoint so users can switch devices.
    """
    return await _verify_jwt(authorization)


async def require_google_admin(authorization: str = Header(...)) -> dict:
    """
    Restrict access to users who signed in via Google (Gmail) and whose
    email is listed in the ADMIN_EMAILS env var (comma-separated).
    Does NOT enforce device binding — admin uses a browser, not the app.
    """
    user = await _verify_jwt(authorization)

    firebase_info = user.get("firebase", {})
    if firebase_info.get("sign_in_provider") != "google.com":
        raise HTTPException(status_code=403, detail="Admin access requires Google sign-in")

    admin_emails = [
        e.strip().lower()
        for e in os.getenv("ADMIN_EMAILS", "").split(",")
        if e.strip()
    ]
    if not admin_emails:
        raise HTTPException(status_code=503, detail="ADMIN_EMAILS not configured")

    if (user.get("email") or "").lower() not in admin_emails:
        raise HTTPException(status_code=403, detail="This Gmail account is not authorised as admin")

    return user
