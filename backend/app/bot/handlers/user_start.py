import html
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from app.core.config import settings
from app.core.logger import logger
from app.database.session import AsyncSessionLocal
from app.repositories.user_repo import UserRepository
from app.repositories.trade_repo import TradeRepository
from app.services.trade_service import TradeService
from app.bot.keyboards import get_main_menu_keyboard, get_admin_panel_keyboard

router = Router()


@router.message(CommandStart())
async def handle_start(message: Message):
    user = message.from_user
    if not user:
        return

    first_name_safe = html.escape(user.first_name or "کاربر")

    try:
        # Upsert user record
        async with AsyncSessionLocal() as session:
            user_repo = UserRepository(session)
            await user_repo.get_or_create(
                telegram_id=user.id,
                first_name=user.first_name or "کاربر",
                username=user.username
            )
    except Exception as e:
        logger.error(f"Failed to upsert user {user.id} in DB: {e}")

    welcome_text = (
        f"سلام <b>{first_name_safe}</b> عزیز! خوش آمدید 🛡️\n\n"
        f"به <b>دستیار هوشمند معاملاتی و مدیریت ریسک</b> متصل شدید.\n\n"
        f"✨ <b>امکانات کلیدی در دسترس شما:</b>\n"
        f"• <b>ماشین‌حساب پیشرفته و ژورنال:</b> از طریق وب‌اپلیکیشن مینی‌اپ\n"
        f"• <b>ثبت و مدیریت هشدارهای هوشمند قیمت</b> با اعلان آنی در تلگرام\n"
        f"• <b>دیده‌بان زنده تغییرات بازار فیوچرز</b> با آخرین قیمت‌های صرافی\n"
        f"• <b>خلاصه کارنامه و نرخ برد (Win Rate) معاملات شما</b>\n\n"
        f"👇 از منوی زیر بخش مورد نظر خود را انتخاب کنید:"
    )

    try:
        await message.answer(welcome_text, reply_markup=get_main_menu_keyboard(user.id))
    except Exception as e:
        logger.error(f"Error sending start message with keyboard: {e}")
        # Fallback if keyboard still causes an error
        await message.answer(welcome_text)


@router.callback_query(F.data == "btn_miniapp_guide")
async def handle_miniapp_guide(query: CallbackQuery):
    url = (settings.MINI_APP_URL or "").strip()
    text = (
        f"🚀 <b>وضعیت اتصال مینی‌اپ (Telegram Mini App)</b>\n\n"
        f"تلگرام برای باز کردن پنجره وب‌اپلیکیشن در داخل چات، نیازمند <b>آدرس معتبر HTTPS</b> است.\n\n"
        f"🌐 <b>آدرس فعلی تنظیم‌شده:</b>\n<code>{url if url else 'تنظیم نشده'}</code>\n\n"
        f"💡 <b>نحوه فعال‌سازی:</b>\n"
        f"۱. تانل Cloudflare یا دامنه دارای SSL را روی سرور فعال کنید.\n"
        f"۲. آدرس <code>https://...</code> را در فایل <code>.env</code> سرور در متغیر <code>MINI_APP_URL</code> قرار دهید و داکر را ری‌استارت کنید.\n"
        f"۳. همچنین از طریق @BotFather می‌توانید دکمه دائمی Menu Button را به آن متصل کنید."
    )
    await query.message.answer(text)
    await query.answer()


@router.callback_query(F.data == "btn_quick_calc")
async def handle_quick_calc_info(query: CallbackQuery):
    text = (
        f"🧮 <b>راهنمای سریع فرمول مدیریت ریسک</b>\n\n"
        f"در این دستیار، حجم پوزیشن و حد ضرر بر اساس فرمول استاندارد کنترل ریسک محاسبه می‌شود:\n\n"
        f"<code>حجم معامله (سایز) = مقدار ریسک دلاری ÷ فاصله قیمت ورود تا حد ضرر</code>\n"
        f"<code>مارجین مورد نیاز = (حجم معامله × قیمت ورود) ÷ اهرم (Leverage)</code>\n\n"
        f"💡 <b>قاعده طلایی مدیریت ریسک:</b>\n"
        f"همواره در هر پوزیشن حداکثر ۱ تا ۲ درصد از کل سرمایه خود را ریسک کنید. ماشین‌حساب گرافیکی مینی‌اپ این مقادیر و اهرم مجاز را به صورت زنده برای شما محاسبه می‌کند."
    )
    await query.message.answer(text)
    await query.answer()


@router.callback_query(F.data == "btn_help_info")
async def handle_help_info(query: CallbackQuery):
    text = (
        f"ℹ️ <b>راهنما و دستورات کاربردی</b>\n\n"
        f"• <code>/start</code> - بازگشت به منوی اصلی\n"
        f"• <code>/screener</code> - بررسی وضعیت و قیمت‌های لحظه‌ای بازار\n"
        f"• <code>/admin</code> - پنل مدیریت ادمین (مخصوص مدیران ارشد)\n\n"
        f"🛡️ تمامی محاسبات ریاضی با متغیرهای اعشاری بدون خطای ممیز شناور (Decimal Math) انجام می‌شود."
    )
    await query.message.answer(text)
    await query.answer()


@router.callback_query(F.data == "btn_open_admin")
async def handle_open_admin(query: CallbackQuery):
    user = query.from_user
    if not user or user.id not in settings.SUPER_ADMIN_IDS:
        await query.answer("⛔ شما به پنل مدیریت دسترسی ندارید.", show_alert=True)
        return

    await query.message.answer(
        "🛡️ <b>به پنل مدیریت سیستم خوش آمدید:</b>",
        reply_markup=get_admin_panel_keyboard(maintenance_active=False)
    )
    await query.answer()


@router.callback_query(F.data == "btn_portfolio_summary")
async def handle_portfolio_summary(query: CallbackQuery):
    user = query.from_user
    if not user:
        return

    async with AsyncSessionLocal() as session:
        trade_repo = TradeRepository(session)
        trades = await trade_repo.list_by_user(user.id, limit=200)
        stats = TradeService.calculate_portfolio_stats(trades)

    text = (
        f"📊 <b>خلاصه عملکرد ژورنال معاملاتی</b>\n\n"
        f"• کل معاملات ثبت‌شده: <b>{stats['total_trades']}</b>\n"
        f"• معاملات بسته شده: <b>{stats['closed_trades']}</b>\n"
        f"  ├ سودده (TP): <b>{stats['wins']}</b>\n"
        f"  └ زیان‌ده (SL): <b>{stats['losses']}</b>\n"
        f"• نرخ برد (Win Rate): <b>{stats['win_rate']}%</b>\n"
        f"• سود/زیان خالص محقق‌شده: <b>{stats['total_realized_pnl']} USDT</b>\n"
        f"• برترین استراتژی شما: <b>{stats['best_strategy']}</b>\n"
    )

    await query.message.answer(text)
    await query.answer()
