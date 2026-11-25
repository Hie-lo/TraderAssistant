import os
import html
from typing import Optional, Dict, Any, Union
from jinja2 import Environment, TemplateSyntaxError
from aiogram.types import FSInputFile
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.loader import bot
from app.core.config import settings
from app.core.dynamic_config import DynamicConfig
from app.core.exceptions import AppException, BusinessValidationError
from app.core.logger import logger
from app.database.seed import DEFAULT_SETTINGS
from app.models.trade import Trade
from app.repositories.trade_repo import TradeRepository
from app.services.chart_service import ChartService, AUTO_CHARTS_DIR, CUSTOM_CHARTS_DIR
from app.services.market_service import MarketService
from app.services.trade_service import TradeService

_jinja_env = Environment(autoescape=False)
TELEGRAM_CAPTION_LIMIT = 1024


class ChannelService:
    """Renders Jinja2 channel post templates, ensures chart snapshots, and publishes/edits via Aiogram."""

    @staticmethod
    def validate_template(template_str: str) -> None:
        if not template_str or not template_str.strip():
            raise BusinessValidationError("متن قالب نمی‌تواند خالی باشد.")
        try:
            _jinja_env.parse(template_str)
        except TemplateSyntaxError as exc:
            raise BusinessValidationError(f"خطای سینتکس Jinja2 در خط {exc.lineno}: {exc.message}")

    @staticmethod
    def resolve_channel_id() -> Union[int, str]:
        raw = DynamicConfig.get("channel_id")
        if raw is None or str(raw).strip() == "":
            raw = settings.CHANNEL_ID
        if raw is None or str(raw).strip() == "":
            raw = settings.ADMIN_LOG_CHANNEL_ID

        val = str(raw).strip() if raw is not None else ""
        if not val or val == "-1001234567890":
            raise BusinessValidationError("شناسه کانال انتشار (CHANNEL_ID) در تنظیمات یا .env مشخص نشده است.")

        # Numeric IDs (including negative -100...) must be passed as int to Aiogram
        if val.lstrip("-").isdigit():
            return int(val)
        return val

    @classmethod
    def render_caption(cls, trade: Trade, template_str: Optional[str] = None) -> str:
        tpl_source = (
            template_str
            or DynamicConfig.get("channel_post_template")
            or DEFAULT_SETTINGS["channel_post_template"]
        )
        dto = TradeService.trade_to_response(trade)
        context: Dict[str, Any] = {
            "pair": html.escape(dto.pair),
            "symbol": html.escape(trade.symbol),
            "base": html.escape(dto.base),
            "direction": "LONG ▲" if dto.is_long else "SHORT ▼",
            "side": "LONG" if dto.is_long else "SHORT",
            "is_long": dto.is_long,
            "entry": dto.entry_price,
            "entry_price": dto.entry_price,
            "sl": dto.stop_loss,
            "stop_loss": dto.stop_loss,
            "tp": dto.take_profit,
            "take_profit": dto.take_profit,
            "size": dto.size,
            "margin": dto.margin,
            "leverage": dto.leverage,
            "risk_amount": dto.risk_amount,
            "potential_profit": dto.potential_profit,
            "rr": dto.rr,
            "status": dto.status,
            "pnl": dto.realized_pnl or "$0.00",
            "strategy": html.escape(dto.strategy or ""),
            "entry_reason": html.escape(dto.entry_reason or ""),
            "notes": html.escape(dto.notes or ""),
            "date": html.escape(dto.date or ""),
        }

        try:
            rendered = _jinja_env.from_string(tpl_source).render(**context).strip()
        except Exception as exc:
            logger.error(f"Jinja2 template rendering failed for trade {trade.id}: {exc}")
            raise BusinessValidationError(f"خطا در رندر قالب پیام: {exc}")

        if len(rendered) > TELEGRAM_CAPTION_LIMIT:
            rendered = rendered[: TELEGRAM_CAPTION_LIMIT - 3] + "..."
        return rendered

    @staticmethod
    def _resolve_local_chart_path(chart_url: Optional[str]) -> Optional[str]:
        if not chart_url:
            return None
        filename = os.path.basename(chart_url)
        base_dir = CUSTOM_CHARTS_DIR if "charts_custom" in chart_url else AUTO_CHARTS_DIR
        path = os.path.join(base_dir, filename)
        return path if os.path.exists(path) else None

    @classmethod
    async def publish_trade(cls, session: AsyncSession, trade: Trade) -> Trade:
        channel_id = cls.resolve_channel_id()
        trade_repo = TradeRepository(session)

        # Check manually uploaded image first; otherwise strictly generate via CCXT + mplfinance thread
        image_path = (
            cls._resolve_local_chart_path(trade.chart_image_url)
            if trade.is_custom_chart
            else None
        )
        fields_to_save: Dict[str, Any] = {}

        if not image_path:
            timeframe = trade.chart_timeframe or "15m"
            df = await MarketService.fetch_ohlcv_dataframe(
                symbol=trade.symbol,
                timeframe=timeframe,
                limit=80,
                center_price=float(trade.entry_price)
            )
            chart_url = await ChartService.generate_trade_chart(
                trade_id=str(trade.id),
                symbol=trade.symbol,
                timeframe=timeframe,
                entry=float(trade.entry_price),
                sl=float(trade.stop_loss) if trade.stop_loss else None,
                tp=float(trade.take_profit) if trade.take_profit else None,
                df=df
            )
            image_path = cls._resolve_local_chart_path(chart_url)
            fields_to_save["chart_image_url"] = chart_url
            fields_to_save["has_chart_snapshot"] = True

        if not image_path:
            raise AppException("فایل تصویر چارت برای انتشار یافت نشد.", status_code=500)

        caption = cls.render_caption(trade)

        try:
            sent_message = await bot.send_photo(
                chat_id=channel_id,
                photo=FSInputFile(image_path),
                caption=caption
            )
        except TelegramAPIError as exc:
            logger.error(f"Telegram send_photo failed for trade {trade.id} to channel {channel_id}: {exc}")
            raise AppException(f"خطا در ارسال پیام به کانال تلگرام: {exc}", status_code=502)
        except Exception as exc:
            logger.exception(f"Unexpected error publishing trade {trade.id} to channel {channel_id}: {exc}")
            raise AppException(f"خطای غیرمنتظره در انتشار کانال: {exc}", status_code=502)

        fields_to_save["telegram_message_id"] = sent_message.message_id
        updated_trade = await trade_repo.update_fields(trade, fields_to_save)
        logger.info(
            f"Published trade {trade.id} to channel {channel_id} (message_id={sent_message.message_id})"
        )
        return updated_trade

    @classmethod
    async def sync_published_trade_caption(cls, trade: Trade) -> bool:
        """Auto-edits the channel post caption whenever an already-published trade is updated."""
        if not trade.telegram_message_id:
            return False

        try:
            channel_id = cls.resolve_channel_id()
            caption = cls.render_caption(trade)
            await bot.edit_message_caption(
                chat_id=channel_id,
                message_id=trade.telegram_message_id,
                caption=caption
            )
            logger.info(
                f"Auto-edited channel post for trade {trade.id} (message_id={trade.telegram_message_id})"
            )
            return True
        except TelegramBadRequest as exc:
            if "message is not modified" in str(exc).lower():
                logger.debug(f"Channel caption unchanged for trade {trade.id}; skipping Telegram error.")
                return False
            logger.error(f"Telegram edit_message_caption failed for trade {trade.id}: {exc}")
            return False
        except TelegramAPIError as exc:
            logger.error(f"Telegram API error editing caption for trade {trade.id}: {exc}")
            return False
        except Exception as exc:
            logger.exception(f"Unexpected error auto-editing channel post for trade {trade.id}: {exc}")
            return False
