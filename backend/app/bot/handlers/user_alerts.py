from decimal import Decimal
from typing import Union
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from app.core.dynamic_config import DynamicConfig
from app.core.exceptions import BusinessValidationError
from app.core.logger import logger
from app.database.session import AsyncSessionLocal
from app.repositories.alert_repo import AlertRepository
from app.repositories.user_repo import UserRepository
from app.services.alert_service import AlertService
from app.services.pair_service import PairService
from app.bot.states import AlertFSM
from app.bot.keyboards import get_pair_selection_keyboard

router = Router()

_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def _parse_target_number(raw_text: str) -> Decimal:
    normalized = (raw_text or "").translate(_PERSIAN_DIGITS).strip().replace(",", "")
    val = Decimal(normalized)
    if val <= 0:
        raise ValueError("Target price must be positive")
    return val


async def _prompt_target_price(
    reply_target: Message,
    state: FSMContext,
    symbol: str
) -> None:
    """Fetches live price + 24h change and transitions FSM to target price entry."""
    ticker = await PairService.get_pair_ticker(symbol)
    if not ticker or ticker["price"] <= 0:
        await reply_target.answer(
            f"⚠️ دریافت قیمت لحظه‌ای برای <b>{symbol}</b> ناموفق بود. لطفاً نماد دیگری را امتحان کنید:"
        )
        return

    change_pct = ticker["change_pct"]
    change_icon = "🟢" if change_pct >= 0 else "🔴"
    change_sign = "+" if change_pct > 0 else ""

    await state.update_data(symbol=ticker["symbol"], base_price=ticker["price"])
    await state.set_state(AlertFSM.entering_value)

    cancel_kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="❌ انصراف", callback_data="cancel_fsm")]]
    )
    await reply_target.answer(
        f"🪙 نماد: <b>{ticker['symbol']}</b>\n"
        f"💵 قیمت لحظه‌ای: <code>${ticker['price_str']}</code>\n"
        f"📊 تغییرات ۲۴ ساعته: <b>{change_sign}{change_pct:.2f}%</b> {change_icon}\n\n"
        f"🎯 لطفاً <b>قیمت هدف</b> مورد نظر خود را به دلار ارسال کنید (مثلاً <code>{ticker['price_str']}</code>):",
        reply_markup=cancel_kb
    )


@router.callback_query(F.data == "btn_new_alert")
async def start_alert_wizard(query: CallbackQuery, state: FSMContext):
    user = query.from_user
    if not user:
        await query.answer()
        return

    # 1. Freemium / VIP check before entering FSM (DB role as single source of truth)
    async with AsyncSessionLocal() as session:
        user_repo = UserRepository(session)
        db_user = await user_repo.get_or_create(
            telegram_id=user.id,
            first_name=user.first_name or "کاربر",
            username=user.username
        )
        effective_role = await user_repo.resolve_effective_role(db_user)
        active_count = await AlertRepository(session).count_active_by_user(user.id)

    free_max_alerts = int(DynamicConfig.get("free_max_alerts", 3))
    if effective_role == "USER" and active_count >= free_max_alerts:
        await query.message.answer(
            f"🔒 <b>محدودیت حساب رایگان</b>\n\n"
            f"کاربران رایگان مجاز به داشتن حداکثر <b>{free_max_alerts} هشدار قیمت فعال هم‌زمان</b> هستند "
            f"(در حال حاضر {active_count} هشدار فعال دارید).\n\n"
            f"✨ برای ثبت نامحد هشدارهای هوشمند، حساب خود را به <b>VIP</b> ارتقا دهید یا یکی از هشدارهای قبلی را از بخش «📋 هشدارهای فعال من» حذف کنید."
        )
        await query.answer("سقف هشدار رایگان پر شده است.", show_alert=True)
        return

    # 2. Load unified exchange pair list and present paginated keyboard
    pairs = await PairService.get_active_pairs()
    await state.set_state(AlertFSM.choosing_pair)
    await query.message.answer(
        "🔔 <b>ثبت هشدار قیمت هوشمند</b>\n\n"
        "جفت‌ارز مورد نظر را از لیست صفحه‌بندی زیر انتخاب کنید، یا <b>نام ارز را تایپ و ارسال نمایید</b> (مثلاً <code>BTC</code> یا <code>SOL</code>):",
        reply_markup=get_pair_selection_keyboard(pairs=pairs, page=0)
    )
    await query.answer()


@router.callback_query(AlertFSM.choosing_pair, F.data.startswith("alert_page_"))
async def paginate_alert_pairs(query: CallbackQuery):
    try:
        page = int(query.data.replace("alert_page_", ""))
    except ValueError:
        page = 0

    pairs = await PairService.get_active_pairs()
    try:
        await query.message.edit_reply_markup(
            reply_markup=get_pair_selection_keyboard(pairs=pairs, page=page)
        )
    except Exception:
        pass
    await query.answer()


@router.callback_query(F.data == "noop_page")
async def noop_page_callback(query: CallbackQuery):
    await query.answer()


@router.callback_query(AlertFSM.choosing_pair, F.data.startswith("pair_"))
async def choose_pair_button(query: CallbackQuery, state: FSMContext):
    symbol = query.data.replace("pair_", "")
    await _prompt_target_price(query.message, state, symbol)
    await query.answer()


@router.message(AlertFSM.choosing_pair)
async def choose_pair_text(message: Message, state: FSMContext):
    matched = await PairService.find_pair(message.text or "")
    if not matched:
        await message.answer(
            "⚠️ جفت‌ارز با این نام در لیست صرافی یافت نشد.\n"
            "لطفاً نام کوتاه ارز (مثل <code>BTC</code> یا <code>ETHUSDT</code>) را بفرستید یا از دکمه‌های بالا انتخاب کنید:"
        )
        return
    await _prompt_target_price(message, state, matched["symbol"])


@router.message(AlertFSM.entering_value)
async def enter_target_price(message: Message, state: FSMContext):
    user = message.from_user
    if not user:
        return

    try:
        target_price = _parse_target_number(message.text or "")
    except Exception:
        await message.answer("⚠️ لطفاً یک قیمت عددی معتبر و بزرگتر از صفر وارد کنید (مثلاً <code>98500</code>):")
        return

    data = await state.get_data()
    symbol = data.get("symbol", "BTCUSDT")
    base_price = Decimal(str(data.get("base_price", 0)))

    if base_price <= 0:
        ticker = await PairService.get_pair_ticker(symbol)
        if ticker and ticker["price"] > 0:
            base_price = Decimal(str(ticker["price"]))

    if target_price == base_price:
        await message.answer("⚠️ قیمت هدف نمی‌تواند دقیقاً برابر قیمت فعلی باشد. عددی بالاتر یا پایین‌تر وارد کنید:")
        return

    direction = "UP" if target_price > base_price else "DOWN"
    dir_label = "🟢 صعودی (عبور به بالا)" if direction == "UP" else "🔴 نزولی (افت به پایین)"

    try:
        async with AsyncSessionLocal() as session:
            alert = await AlertService.create_alert(
                session=session,
                user_id=user.id,
                symbol=symbol,
                alert_type="PRICE",
                direction=direction,
                base_price=base_price,
                target_value=target_price
            )
            trigger_p = alert.trigger_price

        await message.answer(
            f"✅ <b>هشدار قیمت با موفقیت ثبت شد!</b>\n\n"
            f"• نماد: <b>{symbol}</b>\n"
            f"• جهت: <b>{dir_label}</b>\n"
            f"• قیمت فعلی: <code>${base_price}</code>\n"
            f"• قیمت هدف: <code>${trigger_p}</code>\n\n"
            f"به محض رسیدن قیمت به هدف، پیام هشدار برای شما ارسال خواهد شد."
        )
        await state.clear()
    except BusinessValidationError as e:
        await message.answer(f"🔒 {e.message}")
        await state.clear()
    except Exception as e:
        logger.error(f"Error creating alert for user {user.id} on {symbol}: {e}")
        await message.answer(f"❌ خطا در ثبت هشدار: {e}")
        await state.clear()


@router.callback_query(F.data == "cancel_fsm")
async def cancel_wizard(query: CallbackQuery, state: FSMContext):
    await state.clear()
    await query.message.answer("عملیات لغو شد.")
    await query.answer()


@router.callback_query(F.data == "btn_my_alerts")
async def handle_list_my_alerts(query: CallbackQuery):
    user = query.from_user
    if not user:
        return

    async with AsyncSessionLocal() as session:
        repo = AlertRepository(session)
        alerts = await repo.list_by_user(user.id, limit=20)

    active_alerts = [a for a in alerts if not a.is_triggered]
    if not active_alerts:
        await query.message.answer(
            "📭 شما در حال حاضر هیچ هشدار فعالی ندارید.\n\nاز گزینه «🔔 ثبت هشدار قیمت» می‌توانید هشدار جدید ثبت کنید."
        )
        await query.answer()
        return

    text = "📋 <b>لیست هشدارهای فعال شما:</b>\n\n"
    buttons = []
    for a in active_alerts:
        unit = "%" if a.alert_type == "PERCENT" else "$"
        dir_icon = "🟢" if a.direction == "UP" else "🔴"
        text += (
            f"{dir_icon} <b>{a.symbol}</b> | هدف: <code>{a.target_value}{unit}</code> "
            f"(قیمت تریگر: <code>${a.trigger_price:,.2f}</code>)\n"
        )
        buttons.append([
            InlineKeyboardButton(
                text=f"🗑️ حذف هشدار {a.symbol} ({a.target_value}{unit})",
                callback_data=f"del_alert_{a.id}"
            )
        ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await query.message.answer(text, reply_markup=keyboard)
    await query.answer()


@router.callback_query(F.data.startswith("del_alert_"))
async def handle_delete_alert(query: CallbackQuery):
    if not query.from_user:
        return
    alert_id_str = query.data.replace("del_alert_", "")
    try:
        alert_id = int(alert_id_str)
        async with AsyncSessionLocal() as session:
            repo = AlertRepository(session)
            deleted = await repo.delete_by_id_and_user(alert_id, query.from_user.id)
        if deleted:
            await query.message.answer(f"✅ هشدار شماره {alert_id} با موفقیت حذف شد.")
        else:
            await query.message.answer("⚠️ هشدار یافت نشد یا متعلق به شما نیست.")
    except Exception as e:
        await query.message.answer(f"خطا در حذف هشدار: {e}")
    await query.answer()
