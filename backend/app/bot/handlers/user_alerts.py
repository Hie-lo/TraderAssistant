from decimal import Decimal
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from app.database.session import AsyncSessionLocal
from app.services.alert_service import AlertService
from app.services.market_service import MarketService
from app.bot.states import AlertFSM
from app.bot.keyboards import (
    get_pair_selection_keyboard,
    get_alert_type_keyboard,
    get_direction_keyboard
)
from app.core.exceptions import BusinessValidationError

router = Router()


@router.callback_query(F.data == "btn_new_alert")
async def start_alert_wizard(query: CallbackQuery, state: FSMContext):
    await state.set_state(AlertFSM.choosing_pair)
    await query.message.answer(
        "🔔 <b>مرحله اول:</b> لطفاً جفت‌ارز مورد نظر برای ثبت هشدار را انتخاب کنید:",
        reply_markup=get_pair_selection_keyboard()
    )
    await query.answer()


@router.callback_query(AlertFSM.choosing_pair, F.data.startswith("pair_"))
async def choose_pair(query: CallbackQuery, state: FSMContext):
    symbol = query.data.replace("pair_", "")
    await state.update_data(symbol=symbol)
    await state.set_state(AlertFSM.choosing_type)
    await query.message.answer(
        f"✅ نماد <b>{symbol}</b> انتخاب شد.\n\n"
        f"🎯 <b>مرحله دوم:</b> نوع هشدار را مشخص کنید:",
        reply_markup=get_alert_type_keyboard()
    )
    await query.answer()


@router.callback_query(AlertFSM.choosing_type, F.data.startswith("type_"))
async def choose_type(query: CallbackQuery, state: FSMContext):
    alert_type = query.data.replace("type_", "")
    await state.update_data(alert_type=alert_type)
    await state.set_state(AlertFSM.choosing_direction)
    await query.message.answer(
        "📈 <b>مرحله سوم:</b> جهت فعال‌سازی هشدار را تعیین کنید:",
        reply_markup=get_direction_keyboard()
    )
    await query.answer()


@router.callback_query(AlertFSM.choosing_direction, F.data.startswith("dir_"))
async def choose_direction(query: CallbackQuery, state: FSMContext):
    direction = query.data.replace("dir_", "")
    data = await state.get_data()
    symbol = data.get("symbol", "BTCUSDT")
    alert_type = data.get("alert_type", "PRICE")

    # Fetch live price
    cur_price = await MarketService.fetch_price(symbol)
    live_price_str = f"${cur_price:,.2f}" if cur_price else "در دسترس نیست"

    await state.update_data(direction=direction, base_price=cur_price or 64000.0)
    await state.set_state(AlertFSM.entering_value)

    if alert_type == "PERCENT":
        prompt = (
            f"قیمت فعلی <b>{symbol}</b>: <code>{live_price_str}</code>\n\n"
            f"🔢 لطفاً <b>درصد تغییر مدنظر</b> را به صورت عدد انگلیسی بفرستید (مثلاً <code>5</code> یا <code>2.5</code>):"
        )
    else:
        prompt = (
            f"قیمت فعلی <b>{symbol}</b>: <code>{live_price_str}</code>\n\n"
            f"🎯 لطفاً <b>قیمت دقیق هدف</b> را به دلار بفرستید (مثلاً <code>66000</code>):"
        )

    await query.message.answer(prompt)
    await query.answer()


@router.message(AlertFSM.entering_value)
async def enter_value(message: Message, state: FSMContext):
    user = message.from_user
    text = (message.text or "").strip()

    try:
        target_val = Decimal(text)
        if target_val <= 0:
            raise ValueError()
    except Exception:
        await message.answer("⚠️ لطفاً یک عدد معتبر و بزرگتر از صفر وارد کنید:")
        return

    data = await state.get_data()
    symbol = data.get("symbol", "BTCUSDT")
    alert_type = data.get("alert_type", "PRICE")
    direction = data.get("direction", "UP")
    base_price = Decimal(str(data.get("base_price", 64000.0)))

    try:
        async with AsyncSessionLocal() as session:
            alert = await AlertService.create_alert(
                session=session,
                user_id=user.id,
                symbol=symbol,
                alert_type=alert_type,
                direction=direction,
                base_price=base_price,
                target_value=target_val
            )
            trigger_p = alert.trigger_price

        await message.answer(
            f"✅ <b>هشدار هوشمند با موفقیت ثبت شد!</b>\n\n"
            f"• نماد: <b>{symbol}</b>\n"
            f"• نوع: <b>{alert_type}</b> ({direction})\n"
            f"• قیمت مبدا: <code>${base_price}</code>\n"
            f"• هدف: <b>{target_val}{'%' if alert_type == 'PERCENT' else '$'}</b>\n"
            f"• فعال‌سازی در قیمت: <code>${trigger_p:,.2f}</code>\n\n"
            f"به محض رسیدن قیمت به هدف، پیام هشدار برای شما ارسال خواهد شد."
        )
        await state.clear()
    except BusinessValidationError as e:
        await message.answer(f"❌ خطا: {e.message}\nلطفاً دوباره عدد معتبر بفرستید:")
    except Exception as e:
        await message.answer(f"خطایی رخ داد: {e}")
        await state.clear()


@router.callback_query(F.data == "cancel_fsm")
async def cancel_wizard(query: CallbackQuery, state: FSMContext):
    await state.clear()
    await query.message.answer("عملیات لغو شد.")
    await query.answer()
