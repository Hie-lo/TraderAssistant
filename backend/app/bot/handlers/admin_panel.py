import shutil
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy import text

from app.core.config import settings
from app.core.dynamic_config import DynamicConfig
from app.database.session import AsyncSessionLocal
from app.services.market_service import MarketService
from app.services.admin_service import AdminService
from app.bot.states import AdminFSM
from app.bot.keyboards import get_admin_panel_keyboard

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in settings.SUPER_ADMIN_IDS


@router.message(Command("admin"))
async def open_admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ شما به پنل مدیریت دسترسی ندارید.")
        return

    maint = bool(DynamicConfig.get("maintenance_mode", False))
    await message.answer(
        f"🛡️ <b>پنل مدیریت سیستم و مانیتورینگ</b>\n\n"
        f"• وضعیت سرور: <b>{'حالت تعمیر (Maintenance) ⚠️' if maint else 'عادی و آنلاین ✅'}</b>\n"
        f"• حداکثر اهرم مجاز: <code>{DynamicConfig.get('max_leverage', 2000)}x</code>\n"
        f"• سقف دراوداون پیش‌فرض: <code>{DynamicConfig.get('default_weekly_drawdown_pct', 5.0)}%</code>\n",
        reply_markup=get_admin_panel_keyboard(maint)
    )


@router.callback_query(F.data == "adm_toggle_maint")
async def toggle_maintenance(query: CallbackQuery):
    if not is_admin(query.from_user.id):
        await query.answer("دسترسی رد شد.", show_alert=True)
        return

    current = bool(DynamicConfig.get("maintenance_mode", False))
    new_val = not current

    async with AsyncSessionLocal() as session:
        await AdminService.update_dynamic_config(
            session=session,
            admin_id=query.from_user.id,
            key="maintenance_mode",
            value=new_val,
            description="Toggled via Telegram Admin Panel"
        )

    await query.message.edit_text(
        f"وضعیت حالت تعمیر سرور به <b>{'فعال ⚠️' if new_val else 'غیرفعال ✅'}</b> تغییر یافت.",
        reply_markup=get_admin_panel_keyboard(new_val)
    )
    await query.answer("با موفقیت اعمال شد.")


@router.callback_query(F.data == "adm_watchdog_status")
async def check_watchdog_status(query: CallbackQuery):
    if not is_admin(query.from_user.id):
        await query.answer("دسترسی رد شد.", show_alert=True)
        return

    # 1. DB ping
    db_status = "❌ قطع"
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
            db_status = "✅ متصل (Ping OK)"
    except Exception as e:
        db_status = f"❌ خطا: {e}"

    # 2. CCXT connection
    ccxt_status = "❌ قطع"
    try:
        p = await MarketService.fetch_price("BTCUSDT")
        if p:
            ccxt_status = f"✅ متصل (BTC: ${p:,.2f})"
    except Exception as e:
        ccxt_status = f"❌ خطا: {e}"

    # 3. Disk space
    total, used, free = shutil.disk_usage(".")
    free_gb = free // (2**30)
    free_pct = (free / total) * 100

    report = (
        f"🖥️ <b>گزارش دیده‌بان سلامت سیستم (Watchdog)</b>\n\n"
        f"• پایگاه داده: {db_status}\n"
        f"• فید صرافی بایننس: {ccxt_status}\n"
        f"• فضای خالی دیسک: <b>{free_gb} GB ({free_pct:.1f}%)</b>\n"
        f"• وضعیت کش دسترسی: فعال در حافظه رم\n"
    )

    await query.message.answer(report)
    await query.answer()


@router.callback_query(F.data == "adm_ban_user")
async def start_ban_flow(query: CallbackQuery, state: FSMContext):
    if not is_admin(query.from_user.id):
        await query.answer("دسترسی رد شد.", show_alert=True)
        return

    await state.set_state(AdminFSM.entering_ban_user_id)
    await query.message.answer("شناسه عددی تلگرام (Telegram User ID) کاربر مورد نظر را وارد کنید:")
    await query.answer()


@router.message(AdminFSM.entering_ban_user_id)
async def enter_ban_id(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer("لطفاً یک شناسه عددی معتبر بفرستید:")
        return

    await state.update_data(target_id=int(text))
    await state.set_state(AdminFSM.entering_ban_reason)
    await message.answer("دلیل مسدودسازی را وارد کنید (جهت ثبت در لاگ و نمایش به کاربر):")


@router.message(AdminFSM.entering_ban_reason)
async def enter_ban_reason(message: Message, state: FSMContext):
    reason = (message.text or "").strip()
    data = await state.get_data()
    target_id = data.get("target_id")

    try:
        async with AsyncSessionLocal() as session:
            await AdminService.change_user_status(
                session=session,
                admin_id=message.from_user.id,
                target_user_id=target_id,
                new_status="BANNED",
                ban_reason=reason
            )
        await message.answer(f"✅ کاربر {target_id} با موفقیت به دلیل «{reason}» مسدود (BANNED) شد.")
    except Exception as e:
        await message.answer(f"خطا در مسدودسازی کاربر: {e}")
    finally:
        await state.clear()
