-- Run this in your Supabase SQL editor (Dashboard → SQL Editor → New Query)

CREATE TABLE IF NOT EXISTS public.users (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email               TEXT UNIQUE,
    phone_number        TEXT,
    home_location       JSONB,          -- { "lat": 51.5, "lon": -0.12 }
    alert_threshold     FLOAT DEFAULT 0.5,
    notifications_enabled BOOLEAN DEFAULT true,
    fcm_token           TEXT,           -- Firebase Cloud Messaging device token
    last_alert_sent_at  TIMESTAMPTZ,    -- tracks 1-hour cooldown
    created_at          TIMESTAMPTZ DEFAULT now()
);

-- Index for fast notification queries
CREATE INDEX IF NOT EXISTS idx_users_notifications
    ON public.users (notifications_enabled, fcm_token)
    WHERE notifications_enabled = true AND fcm_token IS NOT NULL;
