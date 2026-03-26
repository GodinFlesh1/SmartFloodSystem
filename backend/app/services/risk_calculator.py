from datetime import datetime, timedelta
from typing import Optional


class RiskCalculator:
    CRITICAL_THRESHOLD = 0.5   # m/hr
    HIGH_THRESHOLD = 0.3
    MEDIUM_THRESHOLD = 0.15

    async def calculate_velocity(self, station_id: str, hours: int = 1) -> Optional[float]:
        """Rate of rise (m/hr) over the given window. Positive = rising."""
        from app.database.db import get_supabase
        supabase = get_supabase()
        now = datetime.utcnow()
        past_time = now - timedelta(hours=hours)

        current = supabase.table('readings') \
            .select('water_level,timestamp') \
            .eq('station_id', station_id) \
            .order('timestamp', desc=True) \
            .limit(1).execute()

        past = supabase.table('readings') \
            .select('water_level,timestamp') \
            .eq('station_id', station_id) \
            .lte('timestamp', past_time.isoformat()) \
            .order('timestamp', desc=True) \
            .limit(1).execute()

        if not current.data or not past.data:
            return None

        diff = current.data[0]['water_level'] - past.data[0]['water_level']
        return round(diff / hours, 4)

    async def assess_risk(self, station_id: str) -> dict:
        v1 = await self.calculate_velocity(station_id, 1)
        v3 = await self.calculate_velocity(station_id, 3)
        v6 = await self.calculate_velocity(station_id, 6)

        risk_level = "LOW"
        risk_score = 0

        if v1 is not None:
            if v1 > self.CRITICAL_THRESHOLD:
                risk_level, risk_score = "CRITICAL", 4
            elif v1 > self.HIGH_THRESHOLD:
                risk_level, risk_score = "HIGH", 3

        if risk_score < 3 and v3 is not None:
            if v3 > self.HIGH_THRESHOLD and risk_score < 3:
                risk_level, risk_score = "HIGH", 3
            elif v3 > self.MEDIUM_THRESHOLD and risk_score < 2:
                risk_level, risk_score = "MEDIUM", 2

        if risk_score < 2 and v6 is not None and v6 > self.MEDIUM_THRESHOLD:
            risk_level, risk_score = "MEDIUM", 2

        return {
            "station_id": station_id,
            "risk_level": risk_level,
            "risk_score": risk_score,
            "velocity_1hr": v1,
            "velocity_3hr": v3,
            "velocity_6hr": v6,
            "assessed_at": datetime.utcnow().isoformat(),
        }
