from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from app.core.config import settings
from app.core.dynamic_config import DynamicConfig


def get_main_menu_keyboard(user_id: int = 0) -> InlineKeyboardMarkup:
    """Main dashboard keyboard with WebApp launch button and quick utilities."""
    url = (settings.MINI_APP_URL or "").strip()
    buttons = []

    # 1. WebApp button if HTTPS configured, otherwise guidance button
    if url.startswith("https://") and "your-domain.com" not in url:
        buttons.append([
            InlineKeyboardButton(
                text="🚀 باز کردن دستیار و ماشین‌حساب (Web App)",
                web_app=WebAppInfo(url=url)
            )
        ])
    else:
        buttons.append([
            InlineKeyboardButton(
                text="🚀 راهنمای اتصال مینی‌اپ (نیاز به HTTPS)",
                callback_data="btn_miniapp_guide"
            )
        ])

    # 2. Alerts management
    buttons.append([
        InlineKeyboardButton(text="🔔 ثبت هشدار قیمت", callback_data="btn_new_alert"),
        InlineKeyboardButton(text="📋 هشدارهای فعال من", callback_data="btn_my_alerts")
    ])

    # 3. Market screener & Portfolio
    buttons.append([
        InlineKeyboardButton(text="📊 دیده‌بان سریع بازار", callback_data="btn_screener"),
        InlineKeyboardButton(text="📈 کارنامه معاملاتی", callback_data="btn_portfolio_summary")
    ])

    # 4. Text calculator & Guide
    buttons.append([
        InlineKeyboardButton(text="🧮 راهنمای محاسبه و ریسک", callback_data="btn_quick_calc"),
        InlineKeyboardButton(text="ℹ️ وضعیت سرور و راهنما", callback_data="btn_help_info")
    ])

    # 5. Super Admin button
    if user_id and user_id in settings.SUPER_ADMIN_IDS:
        buttons.append([
            InlineKeyboardButton(text="🛡️ پنل مدیریت ارشد", callback_data="btn_open_admin")
        ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_pair_selection_keyboard() -> InlineKeyboardMarkup:
    """Pair selection grid for setting alerts."""
    pairs = DynamicConfig.get("supported_pairs", [])
    buttons = []
    row = []
    for p in pairs:
        row.append(InlineKeyboardButton(text=f"{p['icon']} {p['label']}", callback_data=f"pair_{p['symbol']}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="❌ انصراف", callback_data="cancel_fsm")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_alert_type_keyboard() -> InlineKeyboardMarkup:
    """Select between percentage change or absolute price target."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📊 بر اساس درصد تغییر (%)", callback_data="type_PERCENT"),
                InlineKeyboardButton(text="🎯 بر اساس قیمت دقیق ($)", callback_data="type_PRICE")
            ],
            [
                InlineKeyboardButton(text="❌ انصراف", callback_data="cancel_fsm")
            ]
        ]
    )


def get_direction_keyboard() -> InlineKeyboardMarkup:
    """Select alert trigger direction."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🟢 صعودی (عبور به بالا)", callback_data="dir_UP"),
                InlineKeyboardButton(text="🔴 نزولی (افت به پایین)", callback_data="dir_DOWN")
            ],
            [
                InlineKeyboardButton(text="❌ انصراف", callback_data="cancel_fsm")
            ]
        ]
    )


def get_admin_panel_keyboard(maintenance_active: bool) -> InlineKeyboardMarkup:
    """Admin control panel inline keyboard."""
    maint_text = "🔴 خاموش کردن حالت تعمیر" if maintenance_active else "🟢 روشن کردن حالت تعمیر (Maintenance)"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=maint_text, callback_data="adm_toggle_maint")],
            [InlineKeyboardButton(text="🚫 مسدود کردن کاربر", callback_data="adm_ban_user")],
            [InlineKeyboardButton(text="🖥️ بررسی سلامت سیستم و دیده‌بان", callback_data="adm_watchdog_status")]
        ]
    )
