# سند جامع معماری و نقشه راه پروژه: دستیار معاملاتی و مینی‌اپ تلگرام (Trading Assistant & Risk Mini-App)

این سند به عنوان **مرجع واحد حقیقت (Single Source of Truth)** برای توسعه، معماری و ارتباط بین اجزای پروژه طراحی شده است. هر ایجنت هوش مصنوعی (AI Coding Agent) یا توسعه‌دهنده‌ای که روی این پروژه کار می‌کند، موظف است دقیقاً از قوانین، ساختار پوشه‌ها، قراردادهای داده (Data Contracts) و محدودیت‌های ذکرشده در این فایل پیروی کند تا از ایجاد **حلقه‌های باگ (Bug Loops)**، **تداخل Event Loop** و **وابستگی‌های دایره‌ای (Circular Imports)** جلوگیری شود.

---

## ۱. نمای کلی معماری سیستم (Modular Monolith Architecture)

سیستم بر پایه معماری **Modular Monolith ناهمگام (Asynchronous)** روی یک پردازشگر واحد پایتون طراحی شده است که تا سقف ۳۰,۰۰۰ کاربر فعال را بدون نیاز به پیچیدگی میکروسرویس‌ها پشتیبانی می‌کند.

### اجزای اصلی پشته فناوری (Tech Stack):
1. **فرانت‌اند (Telegram Mini-App):**
   * **فریم‌ورک:** React 18 + Tailwind CSS (ساختار SPA).
   * **ارتباط لحظه‌ای قیمت:** اتصال مستقیم مرورگر کاربر به WebSocket عمومی بایننس (`wss://stream.binance.com:9443/ws/<symbol>@trade`).
   * **ارتباط با بک‌اند:** ارسال درخواست‌های REST به همراه هدر امنیتی `X-Telegram-Init-Data`.
2. **بک‌اند و API (Backend Core):**
   * **فریم‌ورک وب:** `FastAPI` (مسئول سرویس‌دهی به مینی‌اپ و مدیریت Webhook/Lifespan).
   * **فریم‌ورک ربات تلگرام:** `Aiogram 3.x` (مدیریت منوهای شیشه‌ای، ماشین حالت FSM برای ثبت هشدارها و ارسال نوتیفیکیشن‌ها).
3. **پایگاه داده (Database Layer):**
   * **موتور دیتابیس:** `PostgreSQL 16`.
   * **ORM و درایور:** `SQLAlchemy 2.0 (Async)` + درایور `asyncpg` + ابزار مهاجرت `Alembic`.
4. **موتور پس‌زمینه و پردازش تصویر (Background & Chart Engine):**
   * **زمان‌بند:** `APScheduler` (نسخه AsyncIOScheduler) برای بررسی هشدارهای قیمتی، غربالگری بازار و بررسی افت سرمایه (Drawdown).
   * **دریافت داده بازار در بک‌اند:** کتابخانه `ccxt.async_support` (نسخه Async).
   * **تولید اسنپ‌شات چارت:** کتابخانه `mplfinance` + `pandas` (اجرا شده در Thread/Process مجزا برای جلوگیری از قفل شدن Event Loop).

---

## ۲. ساختار درختی پروژه و قانون جریان وابستگی (Directory Structure & Import Rules)

ایجنت کدنویس باید دقیقاً ساختار پوشه‌بندی زیر را ایجاد کند:

```text
trading-assistant/
├── docker-compose.yml
├── .env.example
├── backend/
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── alembic/                    # فایل‌های Migration دیتابیس
│   ├── static/
│   │   └── charts/                 # محل ذخیره موقت/دائمی تصاویر چارت تولید شده
│   └── app/
│       ├── __init__.py
│       ├── main.py                 # نقطه ورود اصلی: ترکیب FastAPI + Aiogram + APScheduler در Lifespan
│       ├── config.py               # تنظیمات محیطی با استفاده از pydantic-settings
│       ├── database.py             # تنظیمات AsyncEngine و async_sessionmaker
│       ├── models/                 # لایه ۱: مدل‌های SQLAlchemy (بدون ایمپورت از لایه‌های بالاتر)
│       │   ├── __init__.py
│       │   ├── user.py
│       │   ├── trade.py
│       │   ├── strategy.py
│       │   └── alert.py
│       ├── schemas/                # لایه ۲: مدل‌های اعتبارسنجی Pydantic (ورودی/خروجی API)
│       │   ├── __init__.py
│       │   ├── trade_schema.py
│       │   ├── strategy_schema.py
│       │   └── alert_schema.py
│       ├── repositories/           # لایه ۳: کوئری‌های دیتابیس (فقط با models و database کار می‌کند)
│       │   ├── __init__.py
│       │   ├── user_repo.py
│       │   ├── trade_repo.py
│       │   ├── strategy_repo.py
│       │   └── alert_repo.py
│       ├── services/               # لایه ۴: منطق تجاری، محاسبات، تولید چارت و اتصال به صرافی
│       │   ├── __init__.py
│       │   ├── market_service.py   # ارتباط با ccxt.async_support برای کندل‌ها و غربالگر
│       │   ├── chart_service.py    # تولید عکس چارت با mplfinance در Thread جداگانه
│       │   ├── risk_service.py     # بررسی Max Drawdown و آمار پورتفولیو
│       │   └── alert_worker.py     # بررسی دوره‌ای قیمت‌ها و ارسال پیام از طریق Bot
│       ├── api/                    # لایه ۵ (الف): روت‌های FastAPI برای مینی‌اپ
│       │   ├── __init__.py
│       │   ├── deps.py             # Dependency Injection (تایید هویت initData تلگرام و DB Session)
│       │   └── v1/
│       │       ├── endpoints_trades.py
│       │       ├── endpoints_strategies.py
│       │       └── endpoints_dashboard.py
│       └── bot/                    # لایه ۵ (ب): هندلرهای Aiogram 3.x برای چت تلگرام
│           ├── __init__.py
│           ├── loader.py           # تعریف شیء Bot و Dispatcher
│           ├── states.py           # وضعیت‌های FSM (مثلاً ثبت هشدار قیمتی/درصدی)
│           ├── keyboards.py        # دکمه‌های شیشه‌ای (InlineKeyboards) و دکمه باز کردن Mini-App
│           └── handlers/
│               ├── start.py
│               ├── alerts_fsm.py
│               └── screener.py
└── frontend/                       # کدهای React مینی‌اپلیکیشن
    ├── package.json
    ├── vite.config.js
    └── src/
        ├── App.jsx                 # کامپوننت اصلی مینی‌اپ (ماشین‌حساب، داشبورد، ژورنال، پورتفولیو)
        └── api/
            └── client.js           # تنظیمات fetch/axios با هدر X-Telegram-Init-Data
```

### قانون طلایی جلوگیری از Circular Import (اجباری برای ایجنت):
جریان ایمپورت کردن فایل‌ها باید **تک‌جهته (Unidirectional)** و از بالا به پایین باشد:
$$\text{API / Bot Handlers} \longrightarrow \text{Services} \longrightarrow \text{Repositories} \longrightarrow \text{Models / Schemas} \longrightarrow \text{Database / Config}$$
* **ممنوعیت مطلق:** فایل‌های داخل `models/` یا `repositories/` هرگز نباید چیزی از `services/`، `api/` یا `bot/` ایمپورت کنند.
* **ممنوعیت مطلق:** فایل‌های داخل `api/` نباید چیزی از `bot/handlers/` ایمپورت کنند. اگر API نیاز به ارسال پیام تلگرام داشت، فقط شیء `bot` را از `app.bot.loader` ایمپورت کند.

---

## ۳. طراحی پایگاه داده و اسکیمای PostgreSQL (Database Schema)

تمامی اعداد مالی (قیمت‌ها، حجم‌ها و مبالغ) در دیتابیس باید با نوع `NUMERIC(18, 8)` ذخیره شوند تا خطای گرد شدن اعداد اعشاری (`Float Precision Error`) رخ ندهد.

### جدول ۱: `users` (کاربران)
* `id`: `BIGINT PRIMARY KEY` (همان `telegram_user_id` کاربر بدون نیاز به Auto-increment جداگانه).
* `username`: `VARCHAR(64) NULLABLE`
* `first_name`: `VARCHAR(128)`
* `default_balance`: `NUMERIC(18, 2) DEFAULT 1000.00` (موجودی پایه برای محاسبه افت سرمایه).
* `max_weekly_drawdown_pct`: `NUMERIC(5, 2) DEFAULT 5.00` (سقف مجاز ضرر هفتگی به درصد برای ارسال هشدار).
* `created_at`: `TIMESTAMPTZ DEFAULT NOW()`

### جدول ۲: `strategies` (استراتژی‌های شخصی کاربر)
*(نکته: استراتژی‌های عمومی در کد ثابت هستند و استراتژی‌های شخصی هر کاربر در این جدول ذخیره می‌شوند)*
* `id`: `SERIAL PRIMARY KEY`
* `user_id`: `BIGINT REFERENCES users(id) ON DELETE CASCADE`
* `name`: `VARCHAR(64) NOT NULL`
* **Constraint:** `UNIQUE(user_id, name)` (جلوگیری از ثبت استراتژی تکراری توسط یک کاربر).

### جدول ۳: `trades` (ژورنال معاملات)
* `id`: `UUID PRIMARY KEY DEFAULT gen_random_uuid()`
* `user_id`: `BIGINT REFERENCES users(id) ON DELETE CASCADE` (دارای Index).
* `pair`: `VARCHAR(24) NOT NULL` (مثلاً `BTC/USDT`).
* `symbol`: `VARCHAR(24) NOT NULL` (مثلاً `BTCUSDT` برای کوئری به صرافی).
* `is_long`: `BOOLEAN NOT NULL` (`True` برای Long، `False` برای Short).
* `entry_price`: `NUMERIC(18, 8) NOT NULL`
* `stop_loss`: `NUMERIC(18, 8) NULLABLE` (اختیاری؛ در صورت عدم ورود کاربر `NULL` ذخیره می‌شود).
* `take_profit`: `NUMERIC(18, 8) NULLABLE` (اختیاری).
* `position_size`: `NUMERIC(18, 8) NOT NULL` (حجم ارز محاسبه شده).
* `required_margin`: `NUMERIC(18, 2) NOT NULL` (مارجین درگیر به دلار).
* `leverage`: `INTEGER NOT NULL CHECK (leverage >= 1 AND leverage <= 2000)`
* `risk_amount`: `NUMERIC(18, 2) NOT NULL` (مقدار ریسک دلاری).
* `potential_profit`: `NUMERIC(18, 2) NULLABLE`
* `rr_ratio`: `NUMERIC(10, 2) NULLABLE`
* `status`: `VARCHAR(16) NOT NULL DEFAULT 'OPEN'` (مقادیر مجاز: `'OPEN'`, `'TP'`, `'SL'`, `'DRAW'`).
* `strategy_name`: `VARCHAR(64) NOT NULL DEFAULT 'Price Action'`
* `entry_reason`: `TEXT DEFAULT ''`
* `notes`: `TEXT DEFAULT ''`
* `chart_image_url`: `VARCHAR(512) NULLABLE` (مسیر تصویر اسنپ‌شات چارت، چه خودکار تولید شده باشد چه کاربر آپلود کرده باشد).
* `created_at`: `TIMESTAMPTZ DEFAULT NOW()`
* `closed_at`: `TIMESTAMPTZ NULLABLE`

### جدول ۴: `price_alerts` (هشدارهای هوشمند قیمت و درصد)
* `id`: `SERIAL PRIMARY KEY`
* `user_id`: `BIGINT REFERENCES users(id) ON DELETE CASCADE`
* `symbol`: `VARCHAR(24) NOT NULL` (مثلاً `BTCUSDT`).
* `alert_type`: `VARCHAR(16) NOT NULL` (مقادیر مجاز: `'PRICE'` یا `'PERCENT'`).
* `direction`: `VARCHAR(16) NOT NULL` (مقادیر مجاز: `'UP'` صعودی یا `'DOWN'` نزولی).
* `base_price`: `NUMERIC(18, 8) NOT NULL` (قیمت لحظه‌ای ارز در ثانیه ثبت هشدار).
* `target_value`: `NUMERIC(18, 8) NOT NULL` (اگر نوع `PRICE` باشد همان قیمت هدف است؛ اگر `PERCENT` باشد عدد درصد مثلاً `10` است).
* `trigger_price`: `NUMERIC(18, 8) NOT NULL` (قیمتی که در آن هشدار باید فعال شود؛ در لحظه ثبت محاسبه و ذخیره می‌گردد تا کوئری دیتابیس سریع باشد).
* `is_triggered`: `BOOLEAN DEFAULT FALSE`
* `created_at`: `TIMESTAMPTZ DEFAULT NOW()`

---

## ۴. فرمول‌های ریاضی و منطق محاسباتی (Deterministic Math Specification)

فرانت‌اند (React) و بک‌اند (Python) هر دو باید از فرمول‌های یکسان زیر پیروی کنند:

1. **تبدیل ریسک درصدی و دلاری:**
   $$\text{Risk}_{\$} = \text{Balance} \times \left(\frac{\text{Risk}_{\%}}{100}\right) \quad \Longleftrightarrow \quad \text{Risk}_{\%} = \left(\frac{\text{Risk}_{\$}}{\text{Balance}}\right) \times 100$$

2. **حالت اول: کاربر حد ضرر ($\text{SL}$) را وارد کرده است ($\text{SL} > 0$):**
   * فاصله نسبی حد ضرر از نقطه ورود ($E$):
     $$d_{\text{SL}} = \frac{|E - \text{SL}|}{E}$$
   * ارزش کل پوزیشن ($\text{Position Value}$):
     $$\text{Value} = \frac{\text{Risk}_{\$}}{d_{\text{SL}}}$$
   * حجم پوزیشن به واحد ارز ($\text{Position Size}$):
     $$\text{Size} = \frac{\text{Value}}{E}$$
   * مارجین درگیر ($\text{Required Margin}$) با اهرم $L$:
     $$\text{Margin} = \frac{\text{Value}}{L}$$

3. **حالت دوم: کاربر حد ضرر وارد نکرده است ($\text{SL}$ خالی است):**
   * مقدار ریسک دلاری مستقیماً به عنوان مارجین معامله در نظر گرفته می‌شود:
     $$\text{Margin} = \text{Risk}_{\$}$$
     $$\text{Value} = \text{Margin} \times L$$
     $$\text{Size} = \frac{\text{Value}}{E}$$

4. **محاسبه سود بالقوه و نسبت ریسک به ریوارد ($\text{R/R}$) در صورت وجود حد سود ($\text{TP} > 0$):**
   $$\text{Profit}_{\$} = \text{Size} \times |\text{TP} - E|$$
   $$\text{R/R} = \frac{\text{Profit}_{\$}}{\text{Risk}_{\$}}$$

5. **محاسبه قیمت فعال‌سازی هشدار درصدی در بک‌اند ($\text{Trigger Price}$):**
   * برای جهت صعودی ($\text{UP}$) با درصد $P$:
     $$T_{\text{price}} = \text{BasePrice} \times \left(1 + \frac{P}{100}\right)$$
   * برای جهت نزولی ($\text{DOWN}$) با درصد $P$:
     $$T_{\text{price}} = \text{BasePrice} \times \left(1 - \frac{P}{100}\right)$$

---

## ۵. ارتباطات اجزای کد و جریان داده (Component Communication Flows)

### الف) چرخه حیات یکپارچه در `app/main.py` (یکپارچه‌سازی FastAPI + Aiogram + APScheduler)
برای اینکه دو حلقه رویداد (`asyncio` loop) با هم تداخل پیدا نکنند، **تنها نقطه شروع برنامه `uvicorn app.main:app` است**. در تابع `lifespan` مربوط به FastAPI:
1. اتصال دیتابیس تست می‌شود.
2. زمان‌بند `scheduler.start()` روشن می‌شود (که هر ۳۰ ثانیه تابع `check_price_alerts` را صدا می‌زند).
3. دریافت پیام‌های ربات تلگرام یا از طریق روت Webhook در FastAPI (`POST /webhook/telegram`) انجام می‌شود و یا در محیط توسعه با `asyncio.create_task(dp.start_polling(bot, handle_signals=False))` در پس‌زمینه همان Event Loop بالا می‌آید. **(نکته حیاتی: `handle_signals=False` در Aiogram الزامی است تا کنترل `Ctrl+C` متعلق به Uvicorn مختل نشود).**

### ب) جریان ثبت معامله و تولید خودکار تصویر چارت (Chart Snapshot Pipeline)
وقتی کاربر در مینی‌اپ دکمه «ثبت معامله در ژورنال» را می‌زند:
1. فرانت‌اند درخواست `POST /api/v1/trades` را به همراه JSON معامله به FastAPI می‌فرستد.
2. میدل‌ویر `deps.py` امضای رمزنگاری‌شده `X-Telegram-Init-Data` را با `BOT_TOKEN` چک می‌کند و `user_id` را استخراج می‌نماید.
3. رکورد معامله بلافاصله توسط `trade_repo.py` در جدول `trades` ذخیره شده و پاسخ `201 Created` در کمتر از ۱۰۰ میلی‌ثانیه به مینی‌اپ برمی‌گردد (تا UI کاربر معطل نشود).
4. همزمان، FastAPI یک `BackgroundTasks` به نام `generate_and_attach_chart_task(trade_id)` را اجرا می‌کند:
   * سرویس `market_service.py` با `ccxt.async_support` تعداد ۸۰ کندل تایم‌فریم ۱ ساعته آن نماد را می‌گیرد.
   * سرویس `chart_service.py` با استفاده از `await asyncio.to_thread(render_mplfinance_png, df, entry, sl, tp)` چارت کندل‌استیک را به همراه خطوط افقی نقطه ورود (آبی)، حد ضرر (قرمز) و حد سود (سبز) رسم کرده و در مسیر `static/charts/{trade_id}.png` ذخیره می‌کند.
   * آدرس عکس در فیلد `chart_image_url` آن معامله در دیتابیس آپدیت می‌شود.

### ج) جریان تغییر وضعیت معامله و بررسی افت سرمایه (Drawdown Guard)
وقتی کاربر در ژورنال وضعیت معامله را به `TP`، `SL` یا `DRAW` تغییر می‌دهد و یا یادداشت‌ها را ذخیره می‌کند:
1. فرانت‌اند درخواست `PATCH /api/v1/trades/{trade_id}` را ارسال می‌کند.
2. بک‌اند تغییرات را در PostgreSQL ذخیره می‌کند.
3. اگر وضعیت جدید برابر `SL` (حد ضرر) باشد، سرویس `risk_service.py` فراخوانی می‌شود:
   * مجموع `risk_amount` تمام معاملاتی که در ۷ روز گذشته وضعیت `SL` گرفته‌اند را از دیتابیس جمع می‌زند.
   * اگر نسبت مجموع ضرر به `default_balance` کاربر از `max_weekly_drawdown_pct` (مثلاً ۵٪) عبور کرده باشد، شیء `bot` یک پیام هشدار مدیریت ریسک مستقیم به چت تلگرام کاربر ارسال می‌کند.

---

## ۶. قوانین ضد باگ‌لوپ برای ایجنت کدنویس (Anti-Bug-Loop Guardrails)

ایجنت هوش مصنوعی هنگام نوشتن کدها **موظف** است ۶ قانون زیر را رعایت کند؛ عدم رعایت هر کدام منجر به کرش‌های زنجیره‌ای خواهد شد:

1. **قانون ۱ (عدم مسدودسازی Event Loop با Matplotlib):**
   کتابخانه `matplotlib` و `mplfinance` ذاتاً همگام (Synchronous) هستند و با GUI تداخل دارند. در ابتدای فایل `chart_service.py` **حتماً** باید قبل از هر ایمپورت دیگری نوشته شود:
   ```python
   import matplotlib
   matplotlib.use('Agg') # جلوگیری از کرش عدم وجود Display در سرور لینوکس
   ```
   و تابع رسم چارت **هرگز** نباید مستقیم داخل `async def` اجرا شود، بلکه باید با `await asyncio.to_thread(...)` صدا زده شود.

2. **قانون ۲ (جلوگیری از خطای `MissingGreenlet` در SQLAlchemy Async):**
   در فایل `database.py`، هنگام تعریف `async_sessionmaker`، پارامتر `expire_on_commit=False` **اجباری** است:
   ```python
   AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
   ```
   بدون این پارامتر، خواندن ویژگی‌های یک آبجکت (مثل `trade.id`) بلافاصله بعد از `await session.commit()` باعث کرش برنامه می‌شود.

3. **قانون ۳ (تبدیل Decimal به String/Float در JSON):**
   خروجی فیلدهای `NUMERIC` از PostgreSQL در پایتون از نوع `decimal.Decimal` است. در اسکیماهای Pydantic (`schemas/`) از کانفیگ `model_config = ConfigDict(from_attributes=True)` استفاده کنید و مقادیر عددی را برای فرانت‌اند به صورت `float` یا `str` سریالایز کنید تا جاوااسکریپت در پارس کردن آن دچار خطا نشود.

4. **قانون ۴ (بستن سشن‌های `ccxt.async_support`):**
   هر زمان که از `ccxt.async_support.binance()` استفاده می‌شود، باید در قالب یک Singleton در `market_service.py` مدیریت شود و در هنگام خاموش شدن سرور (بخش خروجی `lifespan` در `main.py`) حتماً متد `await exchange.close()` فراخوانی شود تا خطای `Unclosed client session` در `aiohttp` رخ ندهد.

5. **قانون ۵ (حالت توسعه بدون تلگرام برای تست مینی‌اپ در مرورگر):**
   در فایل `api/deps.py`، اگر متغیر محیطی `ENV_MODE=development` بود و هدر `X-Telegram-Init-Data` خالی بود، به جای برگرداندن خطای `401 Unauthorized`، یک کاربر تست پیش‌فرض (`user_id = 123456789`) برگردانده شود تا بتوان مینی‌اپ را در مرورگر دسکتاپ نیز بدون گیر کردن در احراز هویت تلگرام تست و دیباگ کرد.

6. **قانون ۶ (اعتبارسنجی دوطرفه وضعیت کثیف یا Dirty State در جزئیات معامله):**
   در اندپوینت `PATCH /api/v1/trades/{trade_id}`، تمام فیلدهای ورودی در اسکیمای Pydantic باید `Optional` باشند (`status`, `strategy_name`, `entry_reason`, `notes`, `chart_image_url`) و فقط فیلدهایی که در بدنه درخواست ارسال شده‌اند (`exclude_unset=True`) در دیتابیس آپدیت شوند.

---

## ۷. نقشه راه پیاده‌سازی گام‌به‌گام (Execution Sprints)

ایجنت یا توسعه‌دهنده باید پروژه را دقیقاً به ترتیب ۵ فاز زیر پیاده‌سازی و در پایان هر فاز تست کند:

### فاز ۱: زیرساخت دیتابیس و اسکلت بک‌اند (Foundation & DB)
* [ ] ایجاد `docker-compose.yml` شامل سرویس PostgreSQL.
* [ ] پیاده‌سازی `config.py` و `database.py` با رعایت قانون `expire_on_commit=False`.
* [ ] نوشتن مدل‌های SQLAlchemy (`user.py`, `trade.py`, `strategy.py`, `alert.py`) و ساخت اولین Migration با `Alembic`.
* [ ] **تست فاز ۱:** اجرای موفقیت‌آمیز `alembic upgrade head` و ایجاد جداول در دیتابیس.

### فاز ۲: پیاده‌سازی REST API و اتصال مینی‌اپ (Mini-App Integration)
* [ ] نوشتن اسکیماهای Pydantic و ریپازیتوری‌های `trade_repo.py` و `strategy_repo.py`.
* [ ] پیاده‌سازی اندپوینت‌های:
  * `GET /api/v1/dashboard` (دریافت اطلاعات کاربر، خلاصه پورتفولیو، لیست معاملات و لیست استراتژی‌های شخصی).
  * `POST /api/v1/trades` (ثبت معامله جدید از ماشین‌حساب).
  * `PATCH /api/v1/trades/{trade_id}` (به‌روزرسانی وضعیت `TP/SL/DRAW`، استراتژی، یادداشت‌ها و تصویر چارت).
  * `POST /api/v1/strategies` و `DELETE /api/v1/strategies/{name}` (مدیریت استراتژی‌های شخصی).
* [ ] اتصال کامپوننت React مینی‌اپ (`App.jsx`) به این اندپوینت‌ها.
* [ ] **تست فاز ۲:** ثبت یک معامله در ماشین‌حساب، رفرش کردن صفحه و مشاهده ماندگاری معامله و یادداشت‌ها در PostgreSQL.

### فاز ۳: موتور تولید تصویر چارت و هشدار افت سرمایه (Chart & Risk Engine)
* [ ] پیاده‌سازی `market_service.py` برای دریافت کندل‌های OHLCV با `ccxt.async_support`.
* [ ] پیاده‌سازی `chart_service.py` با `mplfinance` (با رعایت قانون `matplotlib.use('Agg')` و `asyncio.to_thread`) و اتصال آن به `BackgroundTasks` هنگام ثبت معامله.
* [ ] افزودن اندپوینت آپلود تصویر دستی برای زمانی که کاربر می‌خواهد اسکرین‌شات خودش را جایگزین کند.
* [ ] پیاده‌سازی محاسبه Drawdown هفتگی در `risk_service.py`.
* [ ] **تست فاز ۳:** ثبت یک معامله و مشاهده تولید خودکار فایل PNG چارت در پوشه `static/charts/` با خطوط Entry، SL و TP.

### فاز ۴: ربات تعاملی تلگرام، هشدار هوشمند قیمت و غربالگر (Bot & Smart Alerts)
* [ ] راه‌اندازی `Aiogram 3.x` در `bot/` و اتصال آن به `lifespan` در `main.py`.
* [ ] طراحی منوی اصلی شیشه‌ای (Inline Keyboard) شامل دکمه WebApp («باز کردن دستیار و ماشین‌حساب»)، دکمه «ثبت هشدار هوشمند» و دکمه «غربالگر بازار».
* [ ] پیاده‌سازی ماشین حالت (`FSM`) برای ثبت هشدار:
  * انتخاب جفت‌ارز $\leftarrow$ انتخاب نوع (`بر اساس درصد` / `بر اساس قیمت`) $\leftarrow$ انتخاب جهت (`صعودی` / `نزولی`) $\leftarrow$ دریافت عدد معتبر و ذخیره در جدول `price_alerts`.
* [ ] پیاده‌سازی `alert_worker.py` با `APScheduler` برای چک کردن قیمت‌ها در پس‌زمینه و ارسال نوتیفیکیشن تلگرام به محض رسیدن قیمت به `trigger_price`.
* [ ] **تست فاز ۴:** ثبت یک هشدار ۱ درصدی در ربات و دریافت پیام هشدار خودکار از ربات.

### فاز ۵: پولیش نهایی، امنیت و استقرار (Deployment & Security)
* [ ] فعال‌سازی کامل اعتبارسنجی HMAC-SHA256 روی `initData` تلگرام در محیط Production.
* [ ] تنظیم Nginx با گواهی SSL (الزامی برای باز شدن Mini-App در تلگرام).
* [ ] تست بار و بررسی لاگ‌ها.