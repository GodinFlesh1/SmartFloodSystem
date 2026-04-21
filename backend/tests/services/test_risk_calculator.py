import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.risk_calculator import RiskCalculator


def _make_supabase_mock(current_level, past_level):
    """Build a supabase mock returning the given water levels."""
    mock = MagicMock()
    table = MagicMock()
    mock.table.return_value = table
    table.select.return_value = table
    table.eq.return_value = table
    table.order.return_value = table
    table.limit.return_value = table
    table.lte.return_value = table

    current_data = [{"water_level": current_level, "timestamp": "2024-06-01T12:00:00"}] if current_level is not None else []
    past_data    = [{"water_level": past_level,    "timestamp": "2024-06-01T11:00:00"}] if past_level    is not None else []

    current_result = MagicMock(); current_result.data = current_data
    past_result    = MagicMock(); past_result.data    = past_data

    # calculate_velocity calls execute() twice per invocation (current + past)
    table.execute.side_effect = [
        current_result, past_result,   # v1 (1-hour window)
        current_result, past_result,   # v3 (3-hour window)
        current_result, past_result,   # v6 (6-hour window)
    ]
    return mock


# ── calculate_velocity ────────────────────────────────────────────────────────
# get_supabase is imported *inside* calculate_velocity, so the correct
# patch target is the function at its definition site: app.database.db

@pytest.mark.asyncio
async def test_calculate_velocity_rising():
    mock_sb = _make_supabase_mock(2.0, 1.5)
    with patch("app.database.db.get_supabase", return_value=mock_sb):
        calc = RiskCalculator()
        v = await calc.calculate_velocity("station-1", hours=1)
    assert v == pytest.approx(0.5, rel=1e-3)


@pytest.mark.asyncio
async def test_calculate_velocity_no_data():
    mock_sb = _make_supabase_mock(None, None)
    with patch("app.database.db.get_supabase", return_value=mock_sb):
        calc = RiskCalculator()
        v = await calc.calculate_velocity("station-1", hours=1)
    assert v is None


# ── assess_risk — mocking calculate_velocity directly ─────────────────────────

@pytest.mark.asyncio
async def test_assess_risk_critical():
    calc = RiskCalculator()
    with patch.object(calc, "calculate_velocity", new_callable=AsyncMock) as mock_vel:
        mock_vel.side_effect = [0.6, 0.4, 0.2]  # v1, v3, v6
        result = await calc.assess_risk("station-1")

    assert result["risk_level"] == "CRITICAL"
    assert result["risk_score"] == 4
    assert result["velocity_1hr"] == pytest.approx(0.6)


@pytest.mark.asyncio
async def test_assess_risk_high_from_v1():
    calc = RiskCalculator()
    with patch.object(calc, "calculate_velocity", new_callable=AsyncMock) as mock_vel:
        mock_vel.side_effect = [0.4, 0.1, 0.05]
        result = await calc.assess_risk("station-1")

    assert result["risk_level"] == "HIGH"
    assert result["risk_score"] == 3


@pytest.mark.asyncio
async def test_assess_risk_high_from_v3():
    calc = RiskCalculator()
    with patch.object(calc, "calculate_velocity", new_callable=AsyncMock) as mock_vel:
        mock_vel.side_effect = [0.1, 0.35, 0.05]
        result = await calc.assess_risk("station-1")

    assert result["risk_level"] == "HIGH"


@pytest.mark.asyncio
async def test_assess_risk_medium_from_v6():
    calc = RiskCalculator()
    with patch.object(calc, "calculate_velocity", new_callable=AsyncMock) as mock_vel:
        mock_vel.side_effect = [0.1, 0.1, 0.2]
        result = await calc.assess_risk("station-1")

    assert result["risk_level"] == "MEDIUM"
    assert result["risk_score"] == 2


@pytest.mark.asyncio
async def test_assess_risk_low():
    calc = RiskCalculator()
    with patch.object(calc, "calculate_velocity", new_callable=AsyncMock) as mock_vel:
        mock_vel.side_effect = [0.05, 0.05, 0.05]
        result = await calc.assess_risk("station-1")

    assert result["risk_level"] == "LOW"
    assert result["risk_score"] == 0


@pytest.mark.asyncio
async def test_assess_risk_no_data():
    calc = RiskCalculator()
    with patch.object(calc, "calculate_velocity", new_callable=AsyncMock) as mock_vel:
        mock_vel.return_value = None
        result = await calc.assess_risk("station-1")

    assert result["risk_level"] == "LOW"
    assert "assessed_at" in result
