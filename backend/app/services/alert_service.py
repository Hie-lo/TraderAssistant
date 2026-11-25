from decimal import Decimal
from typing import Optional, List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from app.core.config import settings
from app.core.dynamic_config import DynamicConfig
from app.core.exceptions import BusinessValidationError
from app.models.alert import PriceAlert
from app.repositories.alert_repo import AlertRepository
from app.repositories.user_repo import UserRepository
from app.services.market_service import MarketService
from app.core.logger import logger


class AlertService:
    """Service handling smart price and percentage alerts and background triggering."""

    @classmethod
    async def create_alert(
        cls,
        session: AsyncSession,
        user_id: int,
        symbol: str,
        alert_type: str,  # 'PRICE' or 'PERCENT'
        direction: str,   # 'UP' or 'DOWN'
        base_price: Decimal,
        target_value: Decimal
    ) -> PriceAlert:
        alert_repo = AlertRepository(session)

        # Check Freemium / VIP active alerts limit (DB user.role + expiration check)
        user_repo = UserRepository(session)
        db_user = await user_repo.get_by_id(user_id)
        effective_role = await user_repo.resolve_effective_role(db_user)
        if effective_role == "USER":
            max_alerts = int(DynamicConfig.get("free_max_alerts", 3))
            active_count = await alert_repo.count_active_by_user(user_id)
            if active_count >= max_alerts:
                raise BusinessValidationError(
                    f"کاربران رایگان حداکثر مجاز به ثبت {max_alerts} هشدار هم‌زمان هستند. "
                    f"برای ثبت هشدارهای بیشتر حساب خود را به VIP ارتقا دهید یا هشدارهای قبلی را حذف کنید."
                )

        norm_symbol = symbol.replace(" / ", "").replace("/", "").upper()
        if "USDT" not in norm_symbol:
            norm_symbol += "USDT"

        alert_type = alert_type.upper()
        direction = direction.upper()

        if alert_type not in ["PRICE", "PERCENT"]:
            raise BusinessValidationError("نوع هشدار باید PRICE یا PERCENT باشد.")
        if direction not in ["UP", "DOWN"]:
            raise BusinessValidationError("جهت هشدار باید UP یا DOWN باشد.")

        # Deterministic trigger price calculation
        if alert_type == "PRICE":
            trigger_price = target_value
            if direction == "UP" and trigger_price <= base_price:
                raise BusinessValidationError("در هشدار صعودی قیمتی، قیمت هدف باید بالاتر از قیمت فعلی باشد.")
            if direction == "DOWN" and trigger_price >= base_price:
                raise BusinessValidationError("در هشدار نزولی قیمتی، قیمت هدف باید پایین‌تر از قیمت فعلی باشد.")
        else:
            # PERCENT mode
            pct_ratio = target_value / Decimal("100")
            if direction == "UP":
                trigger_price = base_price * (Decimal("1") + pct_ratio)
            else:
                trigger_price = base_price * (Decimal("1") - pct_ratio)

        alert = PriceAlert(
            user_id=user_id,
            symbol=norm_symbol,
            alert_type=alert_type,
            direction=direction,
            base_price=base_price,
            target_value=target_value,
            trigger_price=trigger_price,
            is_triggered=False
        )

        saved = await alert_repo.create(alert)
        logger.info(f"Registered alert #{saved.id} for user {user_id}: {norm_symbol} {direction} at {trigger_price}")
        return saved

    @classmethod
    async def check_all_active_alerts(cls, session: AsyncSession) -> int:
        """Called periodically by scheduler to test active alerts against live market price."""
        alert_repo = AlertRepository(session)
        active_alerts = await alert_repo.get_active_alerts()
        if not active_alerts:
            return 0

        # Group symbols to batch price checks
        symbols = list({a.symbol for a in active_alerts})
        symbol_prices: Dict[str, Optional[float]] = {}
        for sym in symbols:
            symbol_prices[sym] = await MarketService.fetch_price(sym)

        triggered_count = 0
        for alert in active_alerts:
            cur_price = symbol_prices.get(alert.symbol)
            if cur_price is None or cur_price <= 0:
                continue

            current_decimal = Decimal(str(cur_price))
            is_hit = False

            if alert.direction == "UP" and current_decimal >= alert.trigger_price:
                is_hit = True
            elif alert.direction == "DOWN" and current_decimal <= alert.trigger_price:
                is_hit = True

            if is_hit:
                await alert_repo.mark_as_triggered(alert.id)
                triggered_count += 1
                logger.info(f"Triggered alert #{alert.id} for user {alert.user_id} on {alert.symbol} ({current_decimal})")
                await cls._send_alert_notification(alert, current_decimal)

        return triggered_count

    @classmethod
    async def _send_alert_notification(cls, alert: PriceAlert, current_price: Decimal) -> bool:
        if not settings.BOT_TOKEN or "Placeholder" in settings.BOT_TOKEN:
            return False

        arrow = "🟢 صعودی 📈" if alert.direction == "UP" else "🔴 نزولی 📉"
        type_str = f"{alert.target_value}%" if alert.alert_type == "PERCENT" else f"${alert.target_value}"

        text = (
            f"🔔 <b>هشدار هوشمند بازار فعال شد!</b>\n\n"
            f"نماد: <b>{alert.symbol}</b>\n"
            f"جهت حرکت: {arrow}\n"
            f"قیمت مبدا در زمان ثبت: <code>${alert.base_price}</code>\n"
            f"هدف تعیین شده: <b>{type_str}</b>\n"
            f"قیمت تریگر محاسبه شده: <code>${alert.trigger_price}</code>\n"
            f"قیمت فعلی بازار: <b>${current_price}</b>\n\n"
            f"💡 <i>جهت مدیریت پوزیشن یا بررسی ورود، مینی‌اپ را بررسی فرمایید.</i>"
        )

        url = f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": alert.user_id,
            "text": text,
            "parse_mode": "HTML"
        }

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.post(url, json=payload)
                return res.status_code == 200
        except Exception as e:
            logger.warning(f"Failed to deliver alert telegram message to {alert.user_id}: {e}")
            return False
