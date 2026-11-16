from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from app.services.market_service import MarketService

router = Router()


@router.message(Command("screener"))
@router.callback_query(F.data == "btn_screener")
async def show_market_screener(event: Message | CallbackQuery):
    message = event if isinstance(event, Message) else event.message
    if isinstance(event, CallbackQuery):
        await event.answer("در حال دریافت اطلاعات بازار...")

    wait_msg = await message.answer("🔄 در حال دریافت قیمت‌های لحظه‌ای از صرافی...")
    items = await MarketService.get_market_screener()

    lines = ["📊 <b>غربالگر سریع ارزهای برتر (24h Overview)</b>\n"]
    for it in items:
        sym = it["symbol"].replace(":USDT", "")
        p = it["price"]
        ch = it["change_pct"]
        icon = "🟢" if ch >= 0 else "🔴"
        lines.append(f"{icon} <b>{sym}</b>: <code>${p}</code> ({ch:+0.2f}%)")

    lines.append("\n⏱️ <i>به‌روزرسانی لحظه‌ای بر مبنای آخرین معاملات Futures بایننس</i>")
    await wait_msg.edit_text("\n".join(lines))
