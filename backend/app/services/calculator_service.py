from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Tuple
from pydantic import BaseModel
from app.core.dynamic_config import DynamicConfig
from app.core.exceptions import BusinessValidationError


class CalculationResult(BaseModel):
    position_size: Decimal
    position_value: Decimal
    required_margin: Decimal
    risk_amount: Decimal
    risk_percent: Decimal
    potential_profit: Optional[Decimal] = None
    rr_ratio: Optional[Decimal] = None
    is_no_sl_mode: bool = False


class CalculatorService:
    """Deterministic mathematical risk & position sizing engine."""

    @staticmethod
    def _to_decimal(val: any, default: Decimal = Decimal("0")) -> Decimal:
        if val is None or val == "" or val == "—":
            return default
        try:
            return Decimal(str(val))
        except Exception:
            return default

    @classmethod
    def calculate_position(
        cls,
        balance: any,
        risk_value: any,
        risk_type: str,
        entry_price: any,
        stop_loss: any,
        take_profit: any,
        leverage: int,
        is_long: bool
    ) -> CalculationResult:
        b = cls._to_decimal(balance)
        r = cls._to_decimal(risk_value)
        e = cls._to_decimal(entry_price)
        sl = cls._to_decimal(stop_loss)
        tp = cls._to_decimal(take_profit)
        lev = Decimal(str(max(1, leverage)))

        max_lev = DynamicConfig.get("max_leverage", 2000)
        if leverage > max_lev:
            raise BusinessValidationError(f"اهرم انتخابی ({leverage}x) از سقف مجاز سیستم ({max_lev}x) بیشتر است.")

        if b <= Decimal("0"):
            raise BusinessValidationError("موجودی حساب (Balance) باید بزرگتر از صفر باشد.")
        if r <= Decimal("0"):
            raise BusinessValidationError("مقدار ریسک باید بزرگتر از صفر باشد.")
        if e <= Decimal("0"):
            raise BusinessValidationError("قیمت ورود (Entry) باید بزرگتر از صفر باشد.")

        # 1. Calculate risk amount and percent
        if risk_type == "%":
            r_amount = (b * (r / Decimal("100"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            r_percent = r
        else:
            r_amount = r.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            r_percent = ((r / b) * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        if r_amount > b:
            raise BusinessValidationError("مقدار ریسک دلاری نمی‌تواند از کل موجودی بیشتر باشد.")

        is_no_sl = False

        # 2. Mode 1: SL is provided (SL > 0)
        if sl > Decimal("0"):
            if e == sl:
                raise BusinessValidationError("قیمت ورود و حد ضرر نمی‌توانند یکسان باشند.")
            if is_long and sl >= e:
                raise BusinessValidationError("در پوزیشن Long، حد ضرر باید پایین‌تر از نقطه ورود باشد.")
            if not is_long and sl <= e:
                raise BusinessValidationError("در پوزیشن Short، حد ضرر باید بالاتر از نقطه ورود باشد.")

            sl_dist_ratio = abs(e - sl) / e
            p_value = (r_amount / sl_dist_ratio).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            p_size = (p_value / e).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
            r_margin = (p_value / lev).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        else:
            # Mode 2: No SL -> Risk amount acts as required margin
            is_no_sl = True
            r_margin = r_amount
            p_value = (r_margin * lev).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            p_size = (p_value / e).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)

        if r_margin > b:
            raise BusinessValidationError(
                f"مارجین مورد نیاز (${r_margin}) از موجودی حساب (${b}) بیشتر است. اهرم را افزایش دهید."
            )

        # 3. Take Profit & R/R Calculation
        potential_profit: Optional[Decimal] = None
        rr_ratio: Optional[Decimal] = None

        if tp > Decimal("0"):
            valid_tp = (tp > e) if is_long else (tp < e)
            if not valid_tp:
                direction_msg = "بالاتر" if is_long else "پایین‌تر"
                raise BusinessValidationError(f"حد سود در پوزیشن {'Long' if is_long else 'Short'} باید {direction_msg} از نقطه ورود باشد.")

            potential_profit = (p_size * abs(tp - e)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if r_amount > Decimal("0"):
                rr_ratio = (potential_profit / r_amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        return CalculationResult(
            position_size=p_size,
            position_value=p_value,
            required_margin=r_margin,
            risk_amount=r_amount,
            risk_percent=r_percent,
            potential_profit=potential_profit,
            rr_ratio=rr_ratio,
            is_no_sl_mode=is_no_sl
        )
