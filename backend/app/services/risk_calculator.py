from datetime import datetime, timedelta
from typing import Optional

class RiskCalculator:
    # Thresholds in meters per hour
    CRITICAL_THRESHOLD = 0.5
    HIGH_THRESHOLD = 0.3
    MEDIUM_THRESHOLD = 0.15
    
    async def calculate_velocity(self, station_id: str, hours: int = 1) -> Optional[float]:
        """Calculate rate of rise over specified hours"""
        from app.database import supabase
        
        now = datetime.utcnow()
        past_time = now - timedelta(hours=hours)
        
        # Get current reading
        current = supabase.table('readings')\
            .select('water_level, timestamp')\
            .eq('station_id', station_id)\
            .order('timestamp', desc=True)\
            .limit(1)\
            .execute()
        
        # Get past reading
        past = supabase.table('readings')\
            .select('water_level, timestamp')\
            .eq('station_id', station_id)\
            .lte('timestamp', past_time.isoformat())\
            .order('timestamp', desc=True)\
            .limit(1)\
            .execute()
        
        if not current.data or not past.data:
            return None
        
        level_diff = current.data[0]['water_level'] - past.data[0]['water_level']
        velocity = level_diff / hours
        
        return velocity
    
    async def assess_risk(self, station_id: str) -> dict:
        """Assess flood risk based on multiple time windows"""
        velocity_1hr = await self.calculate_velocity(station_id, 1)
        velocity_3hr = await self.calculate_velocity(station_id, 3)
        velocity_6hr = await self.calculate_velocity(station_id, 6)
        
        # Determine risk level
        risk_level = "LOW"
        if velocity_1hr and velocity_1hr > self.CRITICAL_THRESHOLD:
            risk_level = "CRITICAL"
        elif velocity_3hr and velocity_3hr > self.HIGH_THRESHOLD:
            risk_level = "HIGH"
        elif velocity_6hr and velocity_6hr > self.MEDIUM_THRESHOLD:
            risk_level = "MEDIUM"
        
        return {
            "risk_level": risk_level,
            "velocity_1hr": velocity_1hr,
            "velocity_3hr": velocity_3hr,
            "velocity_6hr": velocity_6hr
        }