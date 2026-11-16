from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from app.database.session import AsyncSessionLocal
from app.repositories.user_repo import UserRepository
from app.repositories.trade_repo import TradeRepository
from app.services.trade_service import TradeService
from app.bot.keyboards import get_main_menu_keyboard

router = Router()


@router.message(CommandStart())
async def handle_start(message: Message):
    user = message.from_user
    if not user:
        return

    # Upsert user record
    async with AsyncSessionLocal() as session:
        user_repo = UserRepository(session)
        await user_repo.get_or_create(
            telegram_id=user.id,
            first_name=user.first_name,
            username=user.username
        )

    welcome_text = (
        f"سلام <b>{user.first_name}</b> عزیز! خوش آمدید 🛡️\n\n"
        f"به <b>دستیار هوشمند معاملاتی و ماشین‌حساب مدیریت ریسک</b> متصل شدید.\n\n"
        f"✨ <b>امکانات ویژه:</b>\n"
        f"• محاسبه دقیق حجم، مارجین و ریسک پوزیشن بدون خطا\n"
        f"• ثبت ژورنال خودکار همراه با اسنپ‌شات چارت کندل‌استیک\n"
        f"• رصد افت سرمایه هفتگی و ارسال هشدارهای مدیریت سرمایه\n"
        f"• تعریف هشدارهای هوشمند قیمتی و درصدی\n\n"
        f"برای شروع کار با ماشین‌حساب حرفه‌ای، دکمه زیر را لمس کنید:"
    )

    await message.answer(welcome_text, reply_markup=get_main_menu_keyboard())


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
