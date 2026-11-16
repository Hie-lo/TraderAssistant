# سند مرجع مهندسی بک‌اند، امنیت و یکپارچه‌سازی (Backend Master Blueprint)

این سند، **مشخصات فنی قطعی (Technical Specification)** برای پیاده‌سازی بک‌اند پروژه «دستیار معاملاتی و مینی‌اپ مدیریت ریسک تلگرام» است. تمامی بخش‌های این سند دقیقاً منطبق بر کامپوننت‌های پیاده‌سازی شده در فرانت‌اند (`App.jsx`) و الزامات معماری (معماری لایه‌ای، حذف کامل هاردکد، سیستم مانیتورینگ لحظه‌ای، کنترل دسترسی/مسدودسازی کاربران و امنیت چندلایه) طراحی شده‌اند.

> **دستورالعمل اجباری برای AI Coding Agent:**
> قبل از نوشتن یا ویرایش هر فایلی، بخش مربوط به آن لایه را در این سند مطالعه کن. هیچ متغیر، محدودیت، لیست ارز یا استراتژی را در کدها هاردکد نکن؛ تمامی ارتباطات باید از الگوی `Delivery -> Service -> Repository -> Model` پیروی کنند و هیچ لایه‌ای حق دور زدن لایه پایینی خود را ندارد.

---

## ۱. معماری کلان و ساختار پوشه‌بندی (Layered Service-Repository Architecture)

بک‌اند بر پایه معماری **Modular Monolith ناهمگام (`asyncio`)** با ترکیب `FastAPI` (برای سرویس‌دهی به Mini-App) و `Aiogram 3.x` (برای ربات تلگرام و پنل ادمین) روی دیتابیس `PostgreSQL` اجرا می‌شود.

### ساختار دقیق دایرکتوری‌های بک‌اند

```text
backend/
├── requirements.txt
├── alembic.ini
├── alembic/                        # مدیریت نسخه‌های دیتابیس (Migrations)
├── storage/
│   ├── charts_auto/                # اسنپ‌شات‌های تولید شده توسط mplfinance
│   └── charts_custom/              # تصاویر آپلود و پاک‌سازی شده کاربران
├── logs/                           # فایل‌های لاگ چرخشی (Loguru)
└── app/
    ├── __init__.py
    ├── main.py                     # نقطه ورود واحد: Lifespan، ترکیب FastAPI، Aiogram و Watchdog
    ├── core/                       # هسته مرکزی، امنیت، تنظیمات و مانیتورینگ (پایه‌ترین لایه)
    │   ├── __init__.py
    │   ├── config.py               # تنظیمات زیرساختی ثابت از فایل .env (Pydantic Settings)
    │   ├── dynamic_config.py       # کلاس DynamicConfigManager (کش تنظیمات ادمین در RAM + DB)
    │   ├── security.py             # اعتبارسنجی رمزنگاری HMAC-SHA256 تلگرام (initData)
    │   ├── access_control.py       # کش کاربران مسدود/محدود شده (BannedUsersCache) و RBAC
    │   ├── rate_limiter.py         # محدودکننده نرخ درخواست در RAM + سیستم Auto-Ban ضد اسپم
    │   ├── logger.py               # تنظیمات Loguru + ارسال غیرمسدودکننده خطاها به تلگرام ادمین
    │   └── exceptions.py           # کلاس‌های خطای سفارشی (AppException, RateLimitExceeded, ...)
    ├── database/                   # مدیریت اتصال به PostgreSQL
    │   ├── __init__.py
    │   ├── session.py              # تعریف AsyncEngine و AsyncSessionLocal (expire_on_commit=False)
    │   └── seed.py                 # مقداردهی اولیه تنظیمات پویا، جفت‌ارزها و استراتژی‌ها در اولین اجرا
    ├── models/                     # مدل‌های جداول SQLAlchemy 2.0
    │   ├── __init__.py
    │   ├── base.py                 # کلاس پایه DeclarativeBase و TimestampMixin
    │   ├── user.py                 # مدل User (وضعیت بن، نقش، موجودی پیش‌فرض، سقف دراوداون)
    │   ├── trade.py                # مدل Trade (ژورنال معاملات، منطبق با تمام فیلدهای فرانت‌اند)
    │   ├── strategy.py             # مدل UserStrategy (استراتژی‌های شخصی هر کاربر)
    │   ├── alert.py                # مدل PriceAlert (هشدارهای قیمتی و درصدی)
    │   └── system.py               # مدل‌های SystemSetting (تنظیمات پویا) و AdminAuditLog
    ├── schemas/                    # قراردادهای داده Pydantic v2 (ورودی/خروجی API)
    │   ├── __init__.py
    │   ├── common.py               # پاسخ‌های استاندارد و صفحه‌بندی
    │   ├── dashboard_schema.py     # اسکیمای یکپارچه صفحه اصلی و پورتفولیو
    │   ├── trade_schema.py         # اسکیمای ساخت، ویرایش (Dirty State) و نمایش معامله
    │   ├── strategy_schema.py      # اسکیمای افزودن/حذف استراتژی شخصی
    │   └── admin_schema.py         # اسکیمای تغییر تنظیمات پویا و مدیریت کاربران
    ├── repositories/               # لایه دسترسی به داده (فقط کوئری‌های SQLAlchemy)
    │   ├── __init__.py
    │   ├── base_repo.py            # کلاس جنریک BaseRepository[ModelType] با متدهای CRUD پایه
    │   ├── user_repo.py
    │   ├── trade_repo.py
    │   ├── strategy_repo.py
    │   ├── alert_repo.py
    │   └── system_repo.py
    ├── services/                   # لایه منطق تجاری و محاسبات (مستقل از FastAPI و Aiogram)
    │   ├── __init__.py
    │   ├── calculator_service.py   # اعتبارسنجی ریاضی پوزیشن، مارجین، حجم و حالت بدون SL
    │   ├── trade_service.py        # ثبت ترید، آپدیت ژورنال، آمار پورتفولیو و بهترین استراتژی
    │   ├── chart_service.py        # تولید چارت با mplfinance و اعتبارسنجی امن آپلود عکس با Pillow
    │   ├── market_service.py       # کلاینت Singleton برای ccxt.async_support و کش قیمت‌ها
    │   ├── risk_guard_service.py   # بررسی Drawdown هفتگی پس از ثبت SL و ارسال هشدار
    │   ├── alert_service.py        # منطق ثبت و بررسی هشدارهای قیمتی/درصدی
    │   └── admin_service.py        # بن/آن‌بن کردن کاربر، تغییر تنظیمات پویا و ثبت Audit Log
    ├── api/                        # لایه تحویل وب (FastAPI - مخصوص Mini-App)
    │   ├── __init__.py
    │   ├── deps.py                 # Dependency Injection: احراز هویت، بررسی بن، Rate Limit و سشن DB
    │   ├── middlewares.py          # میدل‌ویر شکار خطاهای سراسری و زمان‌سنجی درخواست‌ها
    │   └── v1/
    │       ├── router.py
    │       ├── bootstrap.py        # دریافت اطلاعات اولیه اپ (کاربر، تنظیمات پویا، جفت‌ارزها، داشبورد)
    │       ├── trades.py           # اندپوینت‌های CRUD معاملات، تغییر وضعیت و آپلود تصویر چارت
    │       ├── strategies.py       # اندپوینت‌های مدیریت استراتژی‌های شخصی
    │       └── admin.py            # اندپوینت‌های مدیریتی ادمین
    └── bot/                        # لایه تحویل تلگرام (Aiogram 3.x)
        ├── __init__.py
        ├── loader.py               # مقداردهی Bot و Dispatcher
        ├── middlewares.py          # میدل‌ویر بررسی بن بودن کاربر، Rate Limit و شکار خطا در بات
        ├── states.py               # ماشین حالت (FSM) برای ثبت هشدار هوشمند و پنل ادمین
        ├── keyboards.py            # کیبوردهای شیشه‌ای (Inline) و دکمه WebAppInfo
        └── handlers/
            ├── user_start.py       # منوی اصلی و لانچر مینی‌اپ
            ├── user_alerts.py      # فرآیند تعاملی ثبت هشدار قیمت/درصد
            ├── user_screener.py    # غربالگر سریع بازار در چت
            └── admin_panel.py      # پنل شیشه‌ای ادمین در تلگرام (بن کاربر، تغییر تنظیمات، وضعیت سرور)
```

### قانون طلایی جریان وابستگی (Strict Import Hierarchy)

برای جلوگیری ۱۰۰٪ از خطای `Circular Import`، جهت ایمپورت‌ها **فقط از چپ به راست** مجاز است:

$$\text{api / bot} \longrightarrow \text{services} \longrightarrow \text{repositories} \longrightarrow \text{models / schemas} \longrightarrow \text{database} \longrightarrow \text{core}$$

1. هیچ فایلی در `repositories/` حق ندارد چیزی از `services/` یا `api/` ایمپورت کند.
2. هیچ فایلی در `services/` حق ندارد `Request` یا `HTTPException` از `FastAPI` و یا `Message` از `Aiogram` ایمپورت کند. لایه سرویس در صورت بروز خطا فقط استثناهای تعریف‌شده در `core/exceptions.py` را `raise` می‌کند.

---

## ۲. سیستم تنظیمات دو لایه و حذف کامل هاردکد (Two-Tier Configuration)

هیچ عدد یا لیست ثابتی (مانند سقف اهرم، لیست ارزها، استراتژی‌های عمومی یا سقف آپلود فایل) نباید در کدهای فرانت‌اند یا بک‌اند هاردکد شود.

### لایه اول: تنظیمات زیرساختی ثابت (`core/config.py`)
تنظیماتی که مربوط به محیط سرور هستند و توسط `pydantic-settings` از فایل `.env` خوانده می‌شوند:
* `ENV_MODE`: مقادیر مجاز `'development'` یا `'production'`.
* `BOT_TOKEN`: توکن ربات تلگرام از BotFather.
* `ADMIN_LOG_CHANNEL_ID`: شناسه عددی کانال/گروه خصوصی تلگرام برای دریافت آنی خطاها و هشدارهای امنیتی.
* `SUPER_ADMIN_IDS`: لیست شناسه‌های تلگرام ادمین‌های اصلی (مثلاً `[123456789]`).
* `DATABASE_URL`: رشته اتصال `postgresql+asyncpg://user:pass@db:5432/trading_db`.
* `MINI_APP_URL`: آدرس HTTPS مینی‌اپ.

### لایه دوم: تنظیمات پویای زمان اجرا (`core/dynamic_config.py`)
تنظیماتی که ادمین می‌تواند در هر لحظه از طریق پنل ادمین (در ربات یا API) بدون ری‌استارت کردن سرور تغییر دهد.

#### جدول دیتابیس `system_settings`:
* `key`: `VARCHAR(64) PRIMARY KEY`
* `value_json`: `JSONB NOT NULL` (ذخیره مقدار به صورت JSON برای پشتیبانی از عدد، بولین، رشته، لیست و دیکشنری)
* `description`: `TEXT`
* `updated_at`: `TIMESTAMPTZ DEFAULT NOW()`
* `updated_by`: `BIGINT NULLABLE`

#### کلیدهای پیش‌فرض در `seed.py` (که در اولین اجرای برنامه در دیتابیس درج می‌شوند):

| کلید تنظیمات (`key`) | مقدار پیش‌فرض (`value_json`) | کاربرد در سیستم و فرانت‌اند |
| :--- | :--- | :--- |
| `maintenance_mode` | `false` | در صورت `true` شدن، کاربران عادی پیام «سیستم در حال بروزرسانی است» می‌گیرند ولی ادمین‌ها دسترسی دارند. |
| `max_leverage` | `2000` | سقف مجاز ورودی اهرم در ماشین‌حساب فرانت‌اند و اعتبارسنجی بک‌اند. |
| `default_weekly_drawdown_pct` | `5.0` | درصد افت سرمایه هفتگی که در صورت عبور کاربر، ربات پیام هشدار مدیریت ریسک می‌فرستد. |
| `max_active_alerts_free` | `5` | حداکثر تعداد هشدارهای قیمت فعال برای هر کاربر عادی. |
| `max_chart_upload_mb` | `2.0` | حداکثر حجم مجاز برای آپلود تصویر چارت توسط کاربر (به مگابایت). |
| `api_rate_limit_per_min` | `60` | حداکثر درخواست مجاز هر کاربر در دقیقه به APIهای عمومی مینی‌اپ. |
| `heavy_rate_limit_per_min` | `6` | حداکثر درخواست مجاز در دقیقه برای عملیات سنگین (تولید چارت و آپلود عکس). |
| `auto_ban_threshold_per_10s` | `50` | اگر کاربری در ۱۰ ثانیه بیش از این تعداد درخواست بفرستد، به صورت خودکار ۱۵ دقیقه `TEMP_BANNED` می‌شود. |
| `telegram_init_data_ttl_sec` | `7200` | مدت اعتبار توکن `initData` تلگرام (۲ ساعت) برای جلوگیری از Replay Attack. |
| `supported_pairs` | لیست JSON شامل `BTCUSDT`, `ETHUSDT`, `SOLUSDT`, `BNBUSDT`, `TONUSDT`, `XRPUSDT` به همراه `step`, `icon`, `color` | ارسال به فرانت‌اند در هنگام لود شدن مینی‌اپ تا لیست جفت‌ارزها و گام فلش‌های بالا/پایین کاملاً پویا باشد. |
| `default_strategies` | لیست JSON شامل `["Price Action", "Smart Money / ICT", "Breakout", ...]` | ارسال به فرانت‌اند برای نمایش در سرچ‌بار استراتژی‌های عمومی. |

#### مکانیزم کلاس `DynamicConfigManager`:
1. در زمان اجرای `lifespan` در `main.py`، متد `await DynamicConfig.load_all(session)` تمام ردیف‌های جدول `system_settings` را می‌خواند و در یک دیکشنری داخل حافظه رم (`_cache: dict[str, Any]`) ذخیره می‌کند.
2. خواندن تنظیمات در کل پروژه با متد `DynamicConfig.get("max_leverage")` با پیچیدگی زمانی $O(1)$ و بدون هیچ کوئری به دیتابیس انجام می‌شود.
3. وقتی ادمین مقداری را تغییر می‌دهد، متد `await DynamicConfig.set(session, key, new_val, admin_id)` هم جدول PostgreSQL را آپدیت می‌کند، هم دیکشنری داخل رم را بلافاصله تغییر می‌دهد و هم یک رکورد در جدول `admin_audit_logs` ثبت می‌کند.

---

## ۳. طراحی کامل جداول دیتابیس (PostgreSQL Schema Specification)

تمامی فیلدهای پولی و قیمتی باید از نوع `NUMERIC(18, 8)` یا `NUMERIC(18, 2)` باشند. استفاده از `FLOAT` برای مقادیر مالی به دلیل خطای دقت اعشاری **ممنوع** است.

### جدول ۱: `users` (کاربران و وضعیت دسترسی)
* `id`: `BIGINT PRIMARY KEY` (شناسه یکتای تلگرام کاربر `telegram_user_id` - بدون Auto Increment).
* `username`: `VARCHAR(64) NULLABLE INDEX`
* `first_name`: `VARCHAR(128) NOT NULL`
* `role`: `VARCHAR(16) NOT NULL DEFAULT 'USER'` (مقادیر: `'USER'`, `'VIP'`, `'ADMIN'`).
* `status`: `VARCHAR(16) NOT NULL DEFAULT 'ACTIVE'` (مقادیر: `'ACTIVE'`, `'RESTRICTED'`, `'TEMP_BANNED'`, `'BANNED'`).
* `banned_until`: `TIMESTAMPTZ NULLABLE` (برای وضعیت `TEMP_BANNED`).
* `ban_reason`: `VARCHAR(256) NULLABLE` (علت محدودیت یا مسدودی جهت نمایش به کاربر).
* `default_balance`: `NUMERIC(18, 2) NOT NULL DEFAULT 1000.00` (آخرین موجودی وارد شده توسط کاربر در ماشین‌حساب).
* `custom_drawdown_limit_pct`: `NUMERIC(5, 2) NULLABLE` (اگر خالی باشد، از `default_weekly_drawdown_pct` تنظیمات پویا استفاده می‌شود).
* `created_at`: `TIMESTAMPTZ NOT NULL DEFAULT NOW()`
* `last_active_at`: `TIMESTAMPTZ NOT NULL DEFAULT NOW()`

### جدول ۲: `user_strategies` (استراتژی‌های شخصی کاربر)
* `id`: `SERIAL PRIMARY KEY`
* `user_id`: `BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE`
* `name`: `VARCHAR(64) NOT NULL`
* `created_at`: `TIMESTAMPTZ NOT NULL DEFAULT NOW()`
* **قید یکتایی:** `UniqueConstraint('user_id', 'name', name='uq_user_strategy_name')`

### جدول ۳: `trades` (ژورنال معاملات - منطبق با فرانت‌اند)
* `id`: `UUID PRIMARY KEY DEFAULT gen_random_uuid()`
* `user_id`: `BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE INDEX`
* `pair`: `VARCHAR(24) NOT NULL` (مثلاً `'BTC / USDT'`).
* `symbol`: `VARCHAR(24) NOT NULL INDEX` (مثلاً `'BTCUSDT'`).
* `base_asset`: `VARCHAR(12) NOT NULL` (مثلاً `'BTC'`).
* `is_long`: `BOOLEAN NOT NULL` (`True` = Long، `False` = Short).
* `entry_price`: `NUMERIC(18, 8) NOT NULL`
* `stop_loss`: `NUMERIC(18, 8) NULLABLE` (اختیاری؛ در صورت عدم ورود کاربر `NULL` ذخیره می‌شود).
* `take_profit`: `NUMERIC(18, 8) NULLABLE` (اختیاری).
* `position_size`: `NUMERIC(18, 8) NOT NULL` (حجم پوزیشن).
* `position_value`: `NUMERIC(18, 2) NOT NULL` (ارزش کل پوزیشن پس از اهرم).
* `required_margin`: `NUMERIC(18, 2) NOT NULL` (مارجین درگیر).
* `leverage`: `INTEGER NOT NULL`
* `risk_amount`: `NUMERIC(18, 2) NOT NULL` (مقدار ریسک دلاری در زمان ثبت).
* `potential_profit`: `NUMERIC(18, 2) NULLABLE` (سود دلاری بالقوه در صورت وجود TP).
* `rr_ratio`: `NUMERIC(10, 2) NULLABLE` (نسبت ریسک به ریوارد).
* `status`: `VARCHAR(16) NOT NULL DEFAULT 'OPEN' INDEX` (مقادیر مجاز: `'OPEN'`, `'TP'`, `'SL'`, `'DRAW'`).
* `realized_pnl`: `NUMERIC(18, 2) NOT NULL DEFAULT 0.00` (محاسبه خودکار در بک‌اند بر اساس `status`: در حالت `TP` برابر `+potential_profit` یا `+risk_amount`، در حالت `SL` برابر `-risk_amount`، در حالت `DRAW` یا `OPEN` برابر `0`).
* `strategy_name`: `VARCHAR(64) NOT NULL DEFAULT 'Price Action'`
* `entry_reason`: `TEXT NOT NULL DEFAULT ''`
* `notes`: `TEXT NOT NULL DEFAULT ''`
* `has_chart_snapshot`: `BOOLEAN NOT NULL DEFAULT FALSE`
* `chart_timeframe`: `VARCHAR(8) NOT NULL DEFAULT '1H'` (مقادیر مجاز: `'15m'`, `'1H'`, `'4H'`).
* `chart_image_url`: `VARCHAR(512) NULLABLE` (مسیر فایل عکس تولید شده یا آپلود شده).
* `is_custom_chart`: `BOOLEAN NOT NULL DEFAULT FALSE` (`True` اگر کاربر خودش عکس آپلود کرده باشد).
* `created_at`: `TIMESTAMPTZ NOT NULL DEFAULT NOW() INDEX`
* `closed_at`: `TIMESTAMPTZ NULLABLE`

### جدول ۴: `price_alerts` (هشدارهای هوشمند قیمت و درصد)
* `id`: `SERIAL PRIMARY KEY`
* `user_id`: `BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE INDEX`
* `symbol`: `VARCHAR(24) NOT NULL INDEX`
* `alert_type`: `VARCHAR(16) NOT NULL` (`'PRICE'` یا `'PERCENT'`).
* `direction`: `VARCHAR(16) NOT NULL` (`'UP'` یا `'DOWN'`).
* `base_price`: `NUMERIC(18, 8) NOT NULL`
* `target_value`: `NUMERIC(18, 8) NOT NULL`
* `trigger_price`: `NUMERIC(18, 8) NOT NULL INDEX`
* `is_triggered`: `BOOLEAN NOT NULL DEFAULT FALSE INDEX`
* `triggered_at`: `TIMESTAMPTZ NULLABLE`
* `created_at`: `TIMESTAMPTZ NOT NULL DEFAULT NOW()`

### جدول ۵: `admin_audit_logs` (ثبت وقایع امنیتی و اقدامات ادمین)
* `id`: `SERIAL PRIMARY KEY`
* `admin_id`: `BIGINT NOT NULL`
* `action`: `VARCHAR(64) NOT NULL` (مثلاً `'BAN_USER'`, `'UPDATE_CONFIG'`, `'AUTO_SHIELD_BAN'`).
* `target_id`: `VARCHAR(64) NULLABLE`
* `details_json`: `JSONB NOT NULL`
* `created_at`: `TIMESTAMPTZ NOT NULL DEFAULT NOW()`

---

## ۴. معماری امنیت، کنترل دسترسی و ضد اسپم (Security & Moderation Engine)

### ۱. اعتبارسنجی رمزنگاری تلگرام (`core/security.py`)
فرانت‌اند در تمامی درخواست‌ها هدر `X-Telegram-Init-Data` (مقدار `window.Telegram.WebApp.initData`) را ارسال می‌کند.
1. تابع `verify_telegram_init_data(init_data_raw: str)` رشته را پارس کرده و فیلد `hash` را جدا می‌کند.
2. سایر کلید-مقدارها را به ترتیب حروف الفبا مرتب کرده و با `\n` به هم می‌چسباند (`data_check_string`).
3. کلید مخفی را با `hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()` می‌سازد.
4. امضای نهایی را محاسبه و با `hmac.compare_digest` مقایسه می‌کند.
5. **بررسی تاریخ انقضا (Anti-Replay):** مقدار `auth_date` را با زمان فعلی سرور مقایسه می‌کند:
   $$\text{now} - \text{auth\_date} \le \text{DynamicConfig.get("telegram\_init\_data\_ttl\_sec")}$$
6. **قانون حالت توسعه (`DEV_MODE`):** فقط و فقط اگر در فایل `.env` مقدار `ENV_MODE=development` باشد و هدر `X-Telegram-Init-Data` برابر رشته `"DEV_MOCK_USER"` یا خالی باشد، سیستم کاربر تستی با `id = 111111111` و `first_name = "امیرحسین"` را برمی‌گرداند تا فرانت‌اند در مرورگر معمولی بدون خطای `401` کار کند. در حالت `production`، نبودن هدر بلافاصله خطای `401 Unauthorized` برمی‌گرداند.

### ۲. مدیریت مسدودسازی و محدودیت در حافظه (`core/access_control.py`)
برای اینکه کاربران مسدودشده نتوانند با ارسال پیام‌های رگباری دیتابیس را درگیر کنند:
* کلاس `AccessControlManager` یک دیکشنری در رم نگه می‌دارد:
  `_restricted_users: dict[int, UserAccessInfo]` شامل `status`, `banned_until`, `ban_reason`.
* در لحظه ورود درخواست (چه در میدل‌ویر `Aiogram` و چه در `deps.py` مربوط به `FastAPI`):
  1. ابتدا بدون باز کردن سشن دیتابیس، `user_id` در `_restricted_users` چک می‌شود.
  2. اگر وضعیت `BANNED` باشد $\leftarrow$ درخواست بلافاصله با کد `403 Forbidden` و پیام `ban_reason` رد می‌شود.
  3. اگر وضعیت `TEMP_BANNED` باشد:
     * اگر $\text{now} < \text{banned\_until}$ باشد $\leftarrow$ درخواست با ذکر زمان باقی‌مانده رد می‌شود.
     * اگر زمان محرومیت تمام شده باشد $\leftarrow$ کاربر به طور خودکار از کشِ مسدودها خارج شده و وضعیتش در دیتابیس به `ACTIVE` برمیگردد.
  4. اگر وضعیت `RESTRICTED` باشد $\leftarrow$ کاربر اجازه خواندن اطلاعات (`GET`) را دارد، اما برای عملیات نوشتن سنگین (آپلود عکس، تولید چارت، ثبت هشدار جدید) خطای `403` دریافت می‌کند.

### ۳. محدودکننده نرخ درخواست و سپر خودکار (`core/rate_limiter.py`)
یک ساختار Sliding Window در حافظه رم (`collections.deque` برای هر `user_id`) پیاده‌سازی می‌شود:
1. **بررسی طوفان درخواست (Auto-Shield):** اگر تعداد درخواست‌های یک کاربر در بازه ۱۰ ثانیه اخیر از `DynamicConfig.get("auto_ban_threshold_per_10s")` (مثلاً ۵۰ درخواست) عبور کند:
   * کاربر بلافاصله به مدت ۱۵ دقیقه در وضعیت `TEMP_BANNED` قرار می‌گیرد.
   * یک هشدار فوری به کانال تلگرام ادمین ارسال می‌شود.
2. **محدودیت عادی API:** بررسی سقف `api_rate_limit_per_min` (پیش‌فرض ۶۰ درخواست در دقیقه).
3. **محدودیت عملیات سنگین (Heavy Endpoint Limiter):** برای اندپوینت‌های تولید تصویر چارت و آپلود عکس، سقف جداگانه `heavy_rate_limit_per_min` (پیش‌فرض ۶ درخواست در دقیقه) اعمال می‌شود.

### ۴. پایپ‌لاین امن آپلود تصویر چارت (`services/chart_service.py`)
وقتی کاربر در صفحه جزئیات ترید دکمه `+ آپلود تصویر` را می‌زند:
1. بررسی سایز بایت‌های دریافتی؛ اگر بیشتر از $\text{max\_chart\_upload\_mb} \times 1024 \times 1024$ بود، خطای `413 Payload Too Large` برگردانده می‌شود.
2. بایت‌ها داخل `io.BytesIO` قرار گرفته و با کتابخانه `Pillow` (`Image.open(stream)`) باز می‌شوند.
3. بررسی فرمت واقعی فایل (`img.format in ['JPEG', 'PNG', 'WEBP']`). این کار جلوی آپلود اسکریپت‌های تغییر نام داده شده به `.png` را می‌گیرد.
4. **پاک‌سازی کامل متادیتا (EXIF Sanitization):** تصویر به فضای رنگی `RGB` تبدیل شده، در صورت بزرگ‌تر بودن ابعاد از `1600x1600` به صورت تناسبی کوچک (`thumbnail`) می‌شود و با نام یکتای `{uuid4().hex}.webp` با کیفیت ۸۵٪ در پوشه `storage/charts_custom/` ذخیره می‌گردد. فایل قبلی (در صورت وجود) از روی دیسک پاک می‌شود تا فضای سرور پر نشود.

---

## ۵. نقشه اتصال دقیق فرانت‌اند به بک‌اند (Frontend-to-Backend API Contracts)

برای اینکه کامپوننت `App.jsx` بدون هیچ تغییری در ساختار ظاهری به بک‌اند وصل شود، ۴ گروه اندپوینت زیر در مسیر `/api/v1` پیاده‌سازی می‌شوند:

### ۱. اندپوینت راه‌انداز اولیه: `GET /api/v1/bootstrap`
در لحظه باز شدن مینی‌اپ، فرانت‌اند فقط **یک درخواست** به این آدرس می‌زند و تمام داده‌های مورد نیاز تب‌های چهارگانه را یکجا دریافت می‌کند:
* **خروجی (`200 OK`):**
```json
{
  "user": {
    "id": 111111111,
    "first_name": "امیرحسین",
    "default_balance": "1000.00",
    "discipline_badge": "سطح انضباط: حرفه‌ای 🛡️",
    "status": "ACTIVE"
  },
  "config": {
    "max_leverage": 2000,
    "pairs": [
      {
        "symbol": "BTCUSDT",
        "label": "BTC / USDT",
        "base": "BTC",
        "icon": "₿",
        "color": "text-yellow-500 bg-yellow-500/10",
        "defaultPrice": "64250.00",
        "step": 50
      }
    ],
    "default_strategies": ["Price Action", "Smart Money / ICT", "Breakout"]
  },
  "custom_strategies": ["ستاپ شخصی فیبوناچی"],
  "trades": [
    {
      "id": "uuid-string",
      "pair": "BTC / USDT",
      "base": "BTC",
      "isLong": true,
      "entryPrice": "62400",
      "stopLoss": "61500",
      "takeProfit": "64800",
      "size": "0.0444",
      "margin": "277.33",
      "leverage": 10,
      "riskAmount": "40.00",
      "potentialProfit": "106.67",
      "rr": "2.67",
      "status": "TP",
      "strategy": "Smart Money / ICT",
      "entryReason": "...",
      "notes": "...",
      "date": "۱۴۰۳/۰۸/۱۲ - ۱۴:۳۰",
      "hasChartSnapshot": true,
      "chartTimeframe": "15m",
      "customChartUrl": "/static/charts_auto/uuid.png"
    }
  ]
}
```
*(نکته مهم نام‌گذاری: در اسکیمای Pydantic از `alias_generator` یا `Field(alias=...)` استفاده شود تا نام فیلدهای خروجی JSON دقیقاً camelCase و هم‌نام متغیرهای `App.jsx` مانند `isLong`, `entryPrice`, `stopLoss`, `hasChartSnapshot` باشند).*

### ۲. ثبت معامله جدید: `POST /api/v1/trades`
وقتی کاربر دکمه «ثبت معامله در ژورنال (+ اسنپ‌شات چارت)» را می‌زند:
1. سرویس `calculator_service.py` مقادیر ورودی را مجدداً با فرمول‌های ریاضی چک می‌کند (اگر `stopLoss` ارسال نشده یا `'—'` باشد، در حالت بدون حد ضرر محاسبه می‌کند) و `default_balance` کاربر را نیز با آخرین `balance` وارد شده آپدیت می‌کند.
2. معامله در جدول `trades` ذخیره می‌شود و بلافاصله به فرانت‌اند برگردانده می‌شود.
3. یک `BackgroundTask` برای تولید تصویر چارت با `mplfinance` اجرا می‌شود:
   * دریافت ۸۰ کندل آخر از بایننس با `ccxt.async_support`.
   * رسم چارت کندل‌استیک با تم تیره (`#0b0f19`)، خط آبی برای `Entry`، خط قرمز نقطه‌چین برای `SL` و خط سبز نقطه‌چین برای `TP`.
   * ذخیره فایل در `storage/charts_auto/{trade_id}_{timeframe}.png` و آپدیت فیلد `chart_image_url` در دیتابیس.

### ۳. ویرایش معامله و تغییر وضعیت (Dirty State): `PATCH /api/v1/trades/{trade_id}`
وقتی کاربر در لیست ژورنال وضعیت را به `TP / SL / DRAW` تغییر می‌دهد و یا در صفحه جزئیات دکمه **«ذخیره تغییرات معامله»** را می‌زند:
* **ورودی (همه فیلدها اختیاری):**
  `status`, `strategy`, `entryReason`, `notes`, `chartTimeframe`, `hasChartSnapshot`.
* **رفتار هوشمند بک‌اند:**
  1. اگر `status` به `'SL'` تغییر پیدا کرد، تابع `risk_guard_service.check_weekly_drawdown(user_id)` صدا زده می‌شود. اگر مجموع ضررهای هفته اخیر از سقف مجاز عبور کرده بود، ربات تلگرام پیام هشدار افت سرمایه را به کاربر ارسال می‌کند.
  2. اگر `chartTimeframe` تغییر کرده بود (مثلاً از `1H` به `15m`) و کاربر عکس دستی آپلود نکرده بود (`is_custom_chart == False`)، تسک پس‌زمینه دوباره چارت را در تایم‌فریم جدید رندر و جایگزین می‌کند.
  3. اگر `hasChartSnapshot` برابر `False` ارسال شد (کاربر دکمه «حذف تصویر چارت» را زد)، فایل تصویر از روی دیسک پاک شده و `chart_image_url = None` می‌شود.

### ۴. آپلود تصویر دستی چارت: `POST /api/v1/trades/{trade_id}/chart-upload`
* دریافت فایل `Multipart/Form-Data`، اعتبارسنجی امن با `Pillow`، ذخیره در `storage/charts_custom/` و بازگرداندن آدرس جدید در فیلد `customChartUrl`.

### ۵. مدیریت استراتژی‌های شخصی:
* `POST /api/v1/strategies`: دریافت `{"name": "ستاپ جدید"}`، ذخیره در جدول `user_strategies`.
* `DELETE /api/v1/strategies/{strategy_name}`: حذف استراتژی شخصی کاربر؛ اگر معامله‌ای از این استراتژی استفاده می‌کرد، استراتژی آن به اولین استراتژی عمومی تغییر می‌یابد.

---

## ۶. سیستم مانیتورینگ، لاگ‌نویسی و اعلان خطا (`core/logger.py`)

برای اینکه ادمین در لحظه از هرگونه باگ یا مشکل زیرساختی مطلع شود، ۳ مکانیزم زیر پیاده‌سازی می‌شود:

### ۱. لاگ‌نویسی ساختاریافته با `Loguru`
* ذخیره لاگ‌های عادی در `logs/app.log` با چرخش روزانه (`rotation="00:00"`) و نگهداری ۱۴ روزه (`retention="14 days"`).
* ذخیره لاگ‌های خطا و امنیتی در فایل مجزای `logs/error.log`.

### ۲. شکارچی سراسری خطا و ارسال به کانال تلگرام ادمین (Telegram Error Notifier)
یک میدل‌ویر سراسری در `FastAPI` و یک `ErrorHandler` سراسری در `Aiogram` قرار می‌گیرد:
* هر زمان خطای پیش‌بینی‌نشده‌ای (`Unhandled Exception`) رخ دهد:
  1. یک کد رهگیری کوتاه (`trace_id = uuid4().hex[:8]`) تولید می‌شود.
  2. به کاربر یک پاسخ ایمن داده می‌شود: `{"detail": "خطای داخلی سرور رخ داد. کد پیگیری: #a1b2c3d4"}` (هرگز متن خطای دیتابیس یا مسیر فایل‌های سرور به کاربر عادی نشان داده نمی‌شود).
  3. یک تسک غیرمسدودکننده (`asyncio.create_task`) پیام زیر را به `ADMIN_LOG_CHANNEL_ID` در تلگرام می‌فرستد:
     * 🚨 **گزارش خطای سیستم (`#a1b2c3d4`)**
     * **بخش:** `API / POST /api/v1/trades` (یا هندلر بات)
     * **کاربر:** `123456789 (@username)`
     * **نوع خطا:** `ZeroDivisionError: division by zero`
     * **محل دقیق:** `services/calculator_service.py:42`
     * **آخرین ۱۰ خط Traceback** در قالب بلوک کد.
* **محافظ ضد اسپم لاگ (Log Deduplication & Throttling):**
  اگر مثلاً دیتابیس قطع شود و در یک دقیقه ۵۰۰ خطای یکسان رخ دهد، سیستم نباید ۵۰۰ پیام به تلگرام ادمین بفرستد (چون تلگرام ربات را بلاک می‌کند). کلاس `TelegramLogNotifier` هشِ خطاها را نگه می‌دارد و هر خطای تکراری را حداکثر **یک بار در هر ۵ دقیقه** به تلگرام ادمین ارسال می‌کند.

### ۳. دیده‌بان سلامت سیستم (`Watchdog` در `APScheduler`)
یک تسک زمان‌بندی شده هر ۲ دقیقه وضعیت حیاتی سرور را چک می‌کند:
1. اجرای کوئری `SELECT 1` روی PostgreSQL و سنجش پینگ دیتابیس.
2. بررسی اتصال به API بایننس (`ccxt`).
3. بررسی فضای خالی دیسک سرور (`shutil.disk_usage`).
اگر هر یک از این موارد دچار اختلال شود یا فضای دیسک به کمتر از ۱۰٪ برسد، فوراً به کانال ادمین هشدار می‌دهد.

---

## ۷. چک‌لیست ضد خطا برای ایجنت کدنویس (Zero-Defect Execution Rules)

ایجنت کدنویس باید در تمام مراحل کدنویسی این ۷ قانون فنی را رعایت کند:

1. **قانون `matplotlib` در سرور بدون گرافیک:**
   در خط اول فایل `services/chart_service.py`، قبل از ایمپورت کردن `mplfinance` یا `pyplot`، حتماً بنویس:
   ```python
   import matplotlib
   matplotlib.use("Agg")
   import mplfinance as mpf
   ```
   و پس از ذخیره هر چارت، حتماً `matplotlib.pyplot.close('all')` را صدا بزن تا نشت حافظه (Memory Leak) در رم سرور رخ ندهد.
2. **اجرای `mplfinance` و `Pillow` در Thread مجزا:**
   چون پردازش تصویر CPU-bound و همگام (Sync) است، همیشه آن‌ها را داخل `await asyncio.to_thread(...)` اجرا کن تا حلقه رویداد `FastAPI` و `Aiogram` حتی برای نیم ثانیه هم قفل نشود.
3. **مدیریت سشن `SQLAlchemy Async`:**
   * هرگز یک `AsyncSession` را بین دو تسک موازی (`asyncio.gather`) به اشتراک نگذار.
   * در `BackgroundTasks` (مثل تسک تولید چارت بعد از ثبت ترید)، از سشنِ مربوط به Request استفاده نکن (چون پس از ارسال پاسخ بسته می‌شود)؛ بلکه داخل تسک پس‌زمینه، یک سشن جدید با `async with AsyncSessionLocal() as bg_session:` باز کن.
4. **بستن تمیز کلاینت `ccxt`:**
   یک نمونه واحد از کلاینت صرافی در `MarketService` بساز و در بخش خروجی `lifespan` در `main.py` حتماً `await MarketService.close()` را فراخوانی کن.
5. **سرو کردن فایل‌های استاتیک چارت:**
   پوشه `storage/` را در `FastAPI` با دستور `app.mount("/static", StaticFiles(directory="storage"), name="static")` مانت کن تا تصاویر چارت مستقیماً در تگ `<img>` فرانت‌اند نمایش داده شوند.
6. **پشتیبانی از تقویم شمسی برای فیلد `date`:**
   فرانت‌اند تاریخ معامله را در فیلد `date` به صورت رشته فارسی (مثلاً `'۱۴۰۳/۰۸/۱۲ - ۱۴:۳۰'`) نمایش می‌دهد. در بک‌اند زمان دقیق را با `TIMESTAMPTZ` در `created_at` ذخیره کن و هنگام تبدیل به JSON برای فرانت‌اند، آن را با کتابخانه `jdatetime` (یا فرمت‌دهی استاندارد) به رشته خوانا تبدیل نما.
7. **پنل ادمین دوگانه:**
   ادمین‌ها بتوانند هم از طریق دستورات شیشه‌ای در ربات تلگرام (`/admin`) و هم از طریق اندپوینت‌های `/api/v1/admin/*` وضعیت کاربران را به `BANNED` / `RESTRICTED` / `ACTIVE` تغییر دهند و مقادیر `DynamicConfig` را ویرایش کنند.

---

## ۸. ترتیب گام‌های کدنویسی (Step-by-Step Build Sequence)

برای اینکه بتوانیم کدها را مرحله‌به‌مرحله بنویسیم، تست کنیم و منطق هر بخش را بررسی کنیم، کدنویسی را دقیقاً در **۵ گام مستقل** پیش می‌بریم:

* **گام اول (هسته پایه و مانیتورینگ):** پیاده‌سازی `core/config.py`، `core/logger.py` (لاگ + گزارشگر تلگرام)، `core/exceptions.py` و `database/session.py`.
* **گام دوم (مدل‌های دیتابیس و تنظیمات پویا):** پیاده‌سازی تمام مدل‌های `models/`، کلاس `DynamicConfigManager` و اسکریپت `seed.py` برای مقادیر پیش‌فرض.
* **گام سوم (امنیت، کنترل دسترسی و Rate Limiter):** پیاده‌سازی `core/security.py` (اعتبارسنجی `initData`)، `core/access_control.py` (کش کاربران مسدود) و `core/rate_limiter.py` (سیستم ضد اسپم و Auto-Ban).
* **گام چهارم (لایه ریپازیتوری، سرویس‌ها و موتور چارت):** پیاده‌سازی `BaseRepository`، سرویس ماشین‌حساب، سرویس ژورنال، سرویس تولید چارت با `mplfinance` و اعتبارسنجی عکس با `Pillow`.
* **گام پنجم (اندپوینت‌های FastAPI، ربات Aiogram و اتصال به فرانت‌اند):** پیاده‌سازی روت‌های `/api/v1/*`، اتصال فرانت‌اند `App.jsx` به بک‌اند واقعی و راه‌اندازی منوهای ربات و پنل ادمین.