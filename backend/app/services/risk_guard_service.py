from decimal import Decimal
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from app.core.config import settings
from app.core.dynamic_config import DynamicConfig
from app.repositories.trade_repo import TradeRepository
from app.repositories.user_repo import UserRepository
from app.core.logger import logger


class RiskGuardService:
    """Monitors weekly account drawdown and triggers Telegram risk mitigation warnings."""

    @classmethod
    async def check_weekly_drawdown(cls, session: AsyncSession, user_id: int) -> bool:
        user_repo = UserRepository(session)
        trade_repo = TradeRepository(session)

        user = await user_repo.get_by_id(user_id)
        if not user or user.default_balance <= Decimal("0"):
            return False

        weekly_losses = await trade_repo.get_weekly_losses(user_id)
        if weekly_losses <= Decimal("0"):
            return False

        limit_pct = (
            user.custom_drawdown_limit_pct
            if user.custom_drawdown_limit_pct is not None
            else Decimal(str(DynamicConfig.get("default_weekly_drawdown_pct", 5.0)))
        )

        loss_pct = (weekly_losses / user.default_balance) * Decimal("100")

        if loss_pct >= limit_pct:
            logger.warning(
                f"User {user_id} exceeded weekly drawdown limit: {loss_pct:.2f}% >= {limit_pct}% "
                f"(Loss: ${weekly_losses} on ${user.default_balance})"
            )
            await cls._send_telegram_drawdown_alert(
                telegram_id=user_id,
                first_name=user.first_name,
                loss_amount=weekly_losses,
                loss_pct=loss_pct,
                limit_pct=limit_pct
            )
            return True

        return False

    @classmethod
    async def _send_telegram_drawdown_alert(
        cls,
        telegram_id: int,
        first_name: str,
        loss_amount: Decimal,
        loss_pct: Decimal,
        limit_pct: Decimal
    ) -> bool:
        """Sends Persian risk alert message to user's Telegram chat."""
        if not settings.BOT_TOKEN or "Placeholder" in settings.BOT_TOKEN:
            return False

        text = (
            f"⚠️ <b>هشدار مدیریت ریسک و افت سرمایه (Drawdown Alert)</b>\n\n"
            f"سلام {first_name} عزیز،\n"
            f"مجموع ضررهای ثبت‌شده شما در ۷ روز گذشته به <b>${loss_amount:,.2f}</b> معادل <b>{loss_pct:.1f}%</b> از موجودی حسابتان رسیده است.\n\n"
            f"🚨 این رقم از سقف مجاز هفتگی شما (<b>{limit_pct}%</b>) عبور کرده است.\n\n"
            f"🛡️ <i>پیشنهاد انضباط معاملاتی:</i>\n"
            f"برای جلوگیری از تله ضررهای متوالی (Revenge Trading)، توصیه می‌شود معاملات خود را برای مدتی متوقف کرده یا حجم پوزیشن‌ها را تا ۵۰٪ کاهش دهید."
        )

        url = f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": telegram_id,
            "text": text,
            "parse_mode": "HTML"
        }

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.post(url, json=payload)
                return res.status_code == 200
        except Exception as e:
            logger.warning(f"Failed to send drawdown telegram alert to user {telegram_id}: {e}")
            return False
