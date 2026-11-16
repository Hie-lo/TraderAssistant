from decimal import Decimal
import pytest
from app.services.calculator_service import CalculatorService
from app.core.exceptions import BusinessValidationError


def test_calculator_mode1_long_with_sl():
    """Test Long position calculation with Stop Loss."""
    res = CalculatorService.calculate_position(
        balance="1000",
        risk_value="2",  # 2% of 1000 = $20
        risk_type="%",
        entry_price="60000",
        stop_loss="58800",  # 2% drop (1200 / 60000 = 0.02)
        take_profit="63000",  # 5% gain (3000 / 60000)
        leverage=10,
        is_long=True
    )

    assert res.risk_amount == Decimal("20.00")
    assert res.position_value == Decimal("1000.00")
    assert res.required_margin == Decimal("100.00")
    assert not res.is_no_sl_mode
    assert res.rr_ratio is not None
    assert res.rr_ratio == Decimal("2.50")


def test_calculator_mode1_short_with_sl():
    """Test Short position calculation with Stop Loss."""
    res = CalculatorService.calculate_position(
        balance="2000",
        risk_value="50",
        risk_type="$",
        entry_price="100.00",
        stop_loss="105.00",  # 5% distance
        take_profit="90.00",   # 10% gain
        leverage=20,
        is_long=False
    )

    assert res.risk_amount == Decimal("50.00")
    assert res.position_value == Decimal("1000.00")
    assert res.required_margin == Decimal("50.00")
    assert res.potential_profit == Decimal("100.00")
    assert res.rr_ratio == Decimal("2.00")


def test_calculator_mode2_no_sl():
    """Test position calculation without SL (margin = risk amount)."""
    res = CalculatorService.calculate_position(
        balance="1000",
        risk_value="50",
        risk_type="$",
        entry_price="50000",
        stop_loss="—",
        take_profit="—",
        leverage=10,
        is_long=True
    )

    assert res.is_no_sl_mode
    assert res.required_margin == Decimal("50.00")
    assert res.position_value == Decimal("500.00")
    assert res.potential_profit is None


def test_calculator_invalid_stop_loss():
    """Test validation errors on wrong SL placement."""
    with pytest.raises(BusinessValidationError, match="پایین‌تر"):
        CalculatorService.calculate_position(
            balance="1000",
            risk_value="20",
            risk_type="$",
            entry_price="60000",
            stop_loss="61000",  # Invalid SL for LONG
            take_profit="—",
            leverage=10,
            is_long=True
        )
