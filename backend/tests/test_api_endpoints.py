import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database.session import AsyncSessionLocal
from app.database.seed import seed_initial_settings
from app.core.dynamic_config import DynamicConfig


@pytest.fixture(autouse=True)
async def setup_test_db():
    from app.database.session import engine, ensure_schema_columns
    from app.models.base import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await ensure_schema_columns(conn)

    async with AsyncSessionLocal() as session:
        await seed_initial_settings(session)
        await DynamicConfig.load_all(session)
    yield


@pytest.mark.asyncio
async def test_health_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_bootstrap_endpoint():
    headers = {"X-Telegram-Init-Data": "DEV_MOCK_USER"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/bootstrap", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "user" in data
    assert data["user"]["id"] == 111111111
    assert "config" in data
    assert "pairs" in data["config"]
    assert len(data["config"]["pairs"]) > 0


@pytest.mark.asyncio
async def test_trades_crud_flow():
    headers = {"X-Telegram-Init-Data": "DEV_MOCK_USER"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Create a trade
        payload = {
            "pair": "BTC / USDT",
            "base": "BTC",
            "isLong": True,
            "entryPrice": "62400.00",
            "stopLoss": "61500.00",
            "takeProfit": "64800.00",
            "leverage": 10,
            "balance": "1000",
            "riskType": "%",
            "riskValue": "2",
            "strategy": "Price Action",
            "entryReason": "Test breakout",
            "notes": "Testing trade flow"
        }
        res = await ac.post("/api/v1/trades", json=payload, headers=headers)
        assert res.status_code == 201
        trade = res.json()
        trade_id = trade["id"]
        assert trade["pair"] == "BTC / USDT"
        assert trade["status"] == "OPEN"

        # 2. Patch dirty state (Change to TP and update notes)
        patch_payload = {
            "status": "TP",
            "notes": "Closed at target with profit!"
        }
        patch_res = await ac.patch(f"/api/v1/trades/{trade_id}", json=patch_payload, headers=headers)
        assert patch_res.status_code == 200
        updated = patch_res.json()
        assert updated["status"] == "TP"
        assert "Closed at target" in updated["notes"]

        # 2.5 Create with stringified numeric fields & omitted base via /api/trades and verify bootstrap persistence
        str_payload = {
            "pair": "ETHUSDT",
            "is_long": True,
            "entry_price": "3400.50",
            "stop_loss": "3300.00",
            "take_profit": "3600.00",
            "size": "0.1990",
            "margin": "67.67",
            "leverage": 10,
            "risk_amount": "20.00",
            "potential_profit": "39.70",
            "rr": "1.99",
            "status": "OPEN",
            "strategy": "Breakout",
        }
        res_str = await ac.post("/api/trades", json=str_payload, headers=headers)
        assert res_str.status_code == 201
        str_trade = res_str.json()
        assert str_trade["base"] == "ETH"
        boot_res = await ac.get("/api/v1/bootstrap", headers=headers)
        assert any(t["id"] == str_trade["id"] for t in boot_res.json()["trades"])
        await ac.delete(f"/api/trades/{str_trade['id']}", headers=headers)

        # 3. Delete trade
        del_res = await ac.delete(f"/api/v1/trades/{trade_id}", headers=headers)
        assert del_res.status_code == 200
        assert del_res.json()["success"] is True

        # Verify not found after delete
        patch_res2 = await ac.patch(f"/api/v1/trades/{trade_id}", json=patch_payload, headers=headers)
        assert patch_res2.status_code == 404


@pytest.mark.asyncio
async def test_strategies_flow():
    headers = {"X-Telegram-Init-Data": "DEV_MOCK_USER"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Add custom strategy
        res = await ac.post("/api/v1/strategies", json={"name": "تست استراتژی هوشمند"}, headers=headers)
        assert res.status_code == 201
        data = res.json()
        assert data["name"] == "تست استراتژی هوشمند"

        # 2. Delete custom strategy
        del_res = await ac.delete(f"/api/v1/strategies/{data['name']}", headers=headers)
        assert del_res.status_code == 200
        del_data = del_res.json()
        assert del_data["success"] is True


@pytest.mark.asyncio
async def test_admin_channel_template_and_publish_flow(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    import pandas as pd
    from app.services import channel_service, market_service
    from app.core.security import AuthenticatedUser

    headers = {"X-Telegram-Init-Data": "DEV_MOCK_USER"}

    # Mock OHLCV DataFrame for deterministic mplfinance rendering without network calls
    idx = pd.date_range("2026-01-01", periods=20, freq="1h")
    sample_df = pd.DataFrame(
        {
            "open": [62000 + i * 20 for i in range(20)],
            "high": [62100 + i * 20 for i in range(20)],
            "low": [61900 + i * 20 for i in range(20)],
            "close": [62050 + i * 20 for i in range(20)],
            "volume": [100.0] * 20,
        },
        index=idx,
    )
    monkeypatch.setattr(market_service.MarketService, "fetch_ohlcv_dataframe", AsyncMock(return_value=sample_df))

    mock_send_photo = AsyncMock(return_value=SimpleNamespace(message_id=98765))
    mock_edit_caption = AsyncMock(return_value=True)
    monkeypatch.setattr(channel_service.bot, "send_photo", mock_send_photo)
    monkeypatch.setattr(channel_service.bot, "edit_message_caption", mock_edit_caption)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Invalid Jinja2 template rejected with 400
        bad_res = await ac.put(
            "/api/admin/template",
            json={"template": "Entry: {{ entry_price", "channelId": "-100999888777"},
            headers=headers,
        )
        assert bad_res.status_code == 400

        # 2. Save valid Jinja2 template & channelId via /api/admin/template
        tpl = "Pair: {{ pair }} | Entry: {{ entry }} | SL: {{ sl }} | Status: {{ status }} | Notes: {{ notes }}"
        put_res = await ac.put(
            "/api/admin/template",
            json={"template": tpl, "channelId": "-100999888777"},
            headers=headers,
        )
        assert put_res.status_code == 200
        assert put_res.json()["success"] is True

        get_res = await ac.get("/api/v1/admin/template", headers=headers)
        assert get_res.status_code == 200
        assert get_res.json()["template"] == tpl
        assert get_res.json()["channelId"] == "-100999888777"

        # 3. Create trade
        create_res = await ac.post(
            "/api/v1/trades",
            json={
                "pair": "BTC / USDT",
                "base": "BTC",
                "isLong": True,
                "entryPrice": "62400.00",
                "stopLoss": "61500.00",
                "takeProfit": "64800.00",
                "leverage": 10,
                "balance": "1000",
                "riskType": "%",
                "riskValue": "2",
                "strategy": "Breakout",
                "notes": "Initial <test> note"
            },
            headers=headers,
        )
        assert create_res.status_code == 201
        trade_id = create_res.json()["id"]

        # 4. Publish trade to channel (triggers mplfinance chart + send_photo)
        pub_res = await ac.post(f"/api/trades/{trade_id}/publish", headers=headers)
        assert pub_res.status_code == 200
        pub_data = pub_res.json()
        assert pub_data["telegramMessageId"] == 98765
        assert mock_send_photo.await_count == 1
        sent_kwargs = mock_send_photo.call_args.kwargs
        assert sent_kwargs["chat_id"] == -100999888777
        assert "Entry: 62400" in sent_kwargs["caption"]
        assert "&lt;test&gt;" in sent_kwargs["caption"]

        # 5. Update trade via PUT /api/trades/{id} -> auto-edits live channel caption
        upd_res = await ac.put(
            f"/api/trades/{trade_id}",
            json={"status": "TP", "notes": "Target hit!"},
            headers=headers,
        )
        assert upd_res.status_code == 200
        assert upd_res.json()["status"] == "TP"
        assert mock_edit_caption.await_count == 1
        edit_kwargs = mock_edit_caption.call_args.kwargs
        assert edit_kwargs["chat_id"] == -100999888777
        assert edit_kwargs["message_id"] == 98765
        assert "Status: TP" in edit_kwargs["caption"]
        assert "Target hit!" in edit_kwargs["caption"]

        # 6. Non-admin RBAC enforcement on admin endpoints
        from app.api.deps import get_current_user
        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
            id=222222222, first_name="Regular", role="USER"
        )
        try:
            forbid_tpl = await ac.get("/api/admin/template", headers=headers)
            assert forbid_tpl.status_code == 403
            forbid_pub = await ac.post(f"/api/trades/{trade_id}/publish", headers=headers)
            assert forbid_pub.status_code == 403
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        # Cleanup trade
        await ac.delete(f"/api/v1/trades/{trade_id}", headers=headers)


@pytest.mark.asyncio
async def test_db_admin_auth_bot_alerts_and_freemium_vip_limits(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from sqlalchemy import delete
    from app.models.user import User
    from app.models.trade import Trade
    from app.models.alert import PriceAlert
    from app.repositories.user_repo import UserRepository
    from app.bot.filters import is_db_admin
    from app.bot.keyboards import get_pair_selection_keyboard
    from app.bot.handlers.user_alerts import start_alert_wizard, choose_pair_text, enter_target_price
    from app.services.pair_service import PairService
    from app.services import market_service
    from app.core.security import AuthenticatedUser
    from app.api.deps import get_current_user
    import pandas as pd

    idx = pd.date_range("2026-01-01", periods=10, freq="1h")
    sample_df = pd.DataFrame(
        {"open": [62000]*10, "high": [62100]*10, "low": [61900]*10, "close": [62050]*10, "volume": [100.0]*10},
        index=idx,
    )
    monkeypatch.setattr(market_service.MarketService, "fetch_ohlcv_dataframe", AsyncMock(return_value=sample_df))

    test_uid = 999888777  # Not in SUPER_ADMIN_IDS

    # Clean test user before run
    async with AsyncSessionLocal() as session:
        await session.execute(delete(PriceAlert).where(PriceAlert.user_id == test_uid))
        await session.execute(delete(Trade).where(Trade.user_id == test_uid))
        await session.execute(delete(User).where(User.id == test_uid))
        await session.commit()

        user = await UserRepository(session).get_or_create(test_uid, "BotTester", "bot_tester", role="USER")
        assert user.role == "USER"

    # 1. Bot DB Admin Check: USER denied, DB-promoted ADMIN granted without .env SUPER_ADMIN_IDS
    assert await is_db_admin(test_uid) is False
    async with AsyncSessionLocal() as session:
        u = await UserRepository(session).get_by_id(test_uid)
        u.role = "ADMIN"
        await session.commit()
    assert await is_db_admin(test_uid) is True

    # Reset back to USER for Freemium/VIP tests
    async with AsyncSessionLocal() as session:
        u = await UserRepository(session).get_by_id(test_uid)
        u.role = "USER"
        await session.commit()

    # 2. Unified PairService + Pagination + Bot Alert FSM + Freemium Alert Limit
    mock_pairs = [
        {"symbol": f"COIN{i}USDT", "label": f"COIN{i} / USDT", "base": f"COIN{i}", "icon": "•", "color": "", "defaultPrice": "100.00", "step": 1.0, "change_pct": 1.5}
        for i in range(15)
    ]
    monkeypatch.setattr(PairService, "get_active_pairs", AsyncMock(return_value=mock_pairs))
    monkeypatch.setattr(
        PairService,
        "get_pair_ticker",
        AsyncMock(return_value={"symbol": "COIN1USDT", "price": 100.0, "price_str": "100.00", "change_pct": 3.25}),
    )

    kb_page0 = get_pair_selection_keyboard(pairs=mock_pairs, page=0, page_size=10)
    kb_page1 = get_pair_selection_keyboard(pairs=mock_pairs, page=1, page_size=10)
    assert any(btn.callback_data == "alert_page_1" for row in kb_page0.inline_keyboard for btn in row)
    assert any(btn.callback_data == "alert_page_0" for row in kb_page1.inline_keyboard for btn in row)

    class DummyState:
        def __init__(self):
            self.state = None
            self.data = {}
        async def set_state(self, s):
            self.state = s
        async def update_data(self, **kw):
            self.data.update(kw)
        async def get_data(self):
            return self.data
        async def clear(self):
            self.state = None

    state = DummyState()
    msg_answers = []

    class DummyMsg:
        def __init__(self, text=""):
            self.text = text
            self.from_user = SimpleNamespace(id=test_uid, first_name="BotTester", username="bot_tester")
        async def answer(self, text, **kwargs):
            msg_answers.append(text)

    dummy_query = SimpleNamespace(
        from_user=SimpleNamespace(id=test_uid, first_name="BotTester", username="bot_tester"),
        message=DummyMsg(),
        answer=AsyncMock(),
    )

    # Set free_max_alerts=1 dynamically to test limit cleanly
    async with AsyncSessionLocal() as session:
        await DynamicConfig.set(session, "free_max_alerts", 1, admin_id=111111111)

    await start_alert_wizard(dummy_query, state)
    assert state.state is not None
    await choose_pair_text(DummyMsg("COIN1"), state)
    assert "3.25%" in msg_answers[-1]
    await enter_target_price(DummyMsg("120"), state)
    assert state.state is None

    # Second alert attempt as USER must be blocked before entering FSM
    await start_alert_wizard(dummy_query, state)
    assert state.state is None
    assert "VIP" in msg_answers[-1]

    # Promote to VIP -> can enter Alert FSM again
    async with AsyncSessionLocal() as session:
        u = await UserRepository(session).get_by_id(test_uid)
        u.role = "VIP"
        await session.commit()
    await start_alert_wizard(dummy_query, state)
    assert state.state is not None

    # 3. Freemium / VIP Trade Limit Enforcement (POST /api/trades)
    async with AsyncSessionLocal() as session:
        u = await UserRepository(session).get_by_id(test_uid)
        u.role = "USER"
        await session.commit()
        await DynamicConfig.set(session, "free_max_trades", 1, admin_id=111111111)

    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        id=test_uid, first_name="BotTester", role="USER"
    )
    try:
        headers = {"X-Telegram-Init-Data": "DEV_MOCK_USER"}
        trade_payload = {
            "pair": "BTC / USDT",
            "base": "BTC",
            "isLong": True,
            "entryPrice": 62000,
            "stopLoss": 61000,
            "takeProfit": 64000,
            "leverage": 10,
            "balance": 1000,
            "riskType": "%",
            "riskValue": 2,
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r1 = await ac.post("/api/trades", json=trade_payload, headers=headers)
            assert r1.status_code == 201
            # 2nd trade for USER at limit 1 -> HTTP 403
            r2 = await ac.post("/api/trades", json=trade_payload, headers=headers)
            assert r2.status_code == 403
            assert "VIP" in r2.json()["detail"]

            # Upgrade to VIP in DB -> succeeds
            async with AsyncSessionLocal() as session:
                u = await UserRepository(session).get_by_id(test_uid)
                u.role = "VIP"
                await session.commit()
            r3 = await ac.post("/api/trades", json=trade_payload, headers=headers)
            assert r3.status_code == 201
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        async with AsyncSessionLocal() as session:
            await DynamicConfig.set(session, "free_max_trades", 15, admin_id=111111111)
            await DynamicConfig.set(session, "free_max_alerts", 3, admin_id=111111111)
            await session.execute(delete(PriceAlert).where(PriceAlert.user_id == test_uid))
            await session.execute(delete(Trade).where(Trade.user_id == test_uid))
            await session.execute(delete(User).where(User.id == test_uid))
            await session.commit()


@pytest.mark.asyncio
async def test_pair_service_unified_pairs(monkeypatch):
    from app.services.pair_service import PairService
    import httpx

    PairService._cached_pairs = []
    PairService._cache_ts = 0.0

    fake_tickers = [
        {"symbol": "ETHUSDT", "lastPrice": "3450.12", "quoteVolume": "500000000", "priceChangePercent": "2.4"},
        {"symbol": "BTCUSDT", "lastPrice": "95000.50", "quoteVolume": "900000000", "priceChangePercent": "-1.1"},
        {"symbol": "USDCUSDT", "lastPrice": "1.00", "quoteVolume": "800000000", "priceChangePercent": "0.0"},
        {"symbol": "BTCUPUSDT", "lastPrice": "10.00", "quoteVolume": "200000000", "priceChangePercent": "3.0"},
    ]

    class FakeResponse:
        status_code = 200
        def json(self):
            return fake_tickers

    class FakeClient:
        def __init__(self, *args, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return False
        async def get(self, url, **kwargs): return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    pairs = await PairService.get_active_pairs(force_refresh=True)
    assert [p["symbol"] for p in pairs] == ["BTCUSDT", "ETHUSDT"]
    assert pairs[0]["defaultPrice"] == "95000.50"
    matched = await PairService.find_pair("eth")
    assert matched is not None and matched["symbol"] == "ETHUSDT"


@pytest.mark.asyncio
async def test_vip_subscription_admin_panel_and_chart_features(monkeypatch):
    import io
    from datetime import datetime, timedelta, timezone
    from unittest.mock import AsyncMock
    from PIL import Image
    import pandas as pd
    from sqlalchemy import delete
    from app.models.user import User
    from app.models.trade import Trade
    from app.models.payment import Payment
    from app.repositories.user_repo import UserRepository
    from app.services.chart_service import ChartService
    from app.services import market_service
    from app.core.security import AuthenticatedUser
    from app.api.deps import get_current_user

    test_uid = 888777666
    async with AsyncSessionLocal() as session:
        await session.execute(delete(Payment).where(Payment.user_id == test_uid))
        await session.execute(delete(Trade).where(Trade.user_id == test_uid))
        await session.execute(delete(User).where(User.id == test_uid))
        await session.commit()
        await UserRepository(session).get_or_create(test_uid, "VipApplicant", "vip_app", role="USER")

    idx = pd.date_range("2026-01-01", periods=20, freq="15min")
    sample_df = pd.DataFrame(
        {
            "open": [62000 + i * 10 for i in range(20)],
            "high": [62050 + i * 10 for i in range(20)],
            "low": [61950 + i * 10 for i in range(20)],
            "close": [62020 + i * 10 for i in range(20)],
            "volume": [100.0] * 20,
        },
        index=idx,
    )
    monkeypatch.setattr(market_service.MarketService, "fetch_ohlcv_dataframe", AsyncMock(return_value=sample_df))

    # 1. Verify ChartService.render_chart_bytes generates PNG strictly in memory (BytesIO)
    chart_bytes = await ChartService.render_chart_bytes("BTCUSDT", "15m", 62100.0, 61900.0, 62400.0, sample_df)
    assert chart_bytes.startswith(b"\x89PNG")

    # Build a small valid PNG receipt in memory
    img_buf = io.BytesIO()
    Image.new("RGB", (60, 60), color=(30, 144, 255)).save(img_buf, format="PNG")
    receipt_bytes = img_buf.getvalue()

    headers = {"X-Telegram-Init-Data": "DEV_MOCK_USER"}
    try:
        # Step A: User submits VIP receipt & creates a trade (locked to 15m)
        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
            id=test_uid, first_name="VipApplicant", role="USER"
        )
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            plans_res = await ac.get("/api/vip/plans", headers=headers)
            assert plans_res.status_code == 200
            assert "vipPrices" in plans_res.json()

            pay_res = await ac.post(
                "/api/payments",
                data={"plan_duration": "3"},
                files={"file": ("receipt.png", receipt_bytes, "image/png")},
                headers=headers,
            )
            assert pay_res.status_code == 201
            payment_id = pay_res.json()["payment"]["id"]

            tr_res = await ac.post(
                "/api/trades",
                json={
                    "pair": "BTC / USDT",
                    "base": "BTC",
                    "isLong": True,
                    "entryPrice": 62100,
                    "stopLoss": 61900,
                    "takeProfit": 62400,
                    "leverage": 10,
                    "balance": 1000,
                    "riskType": "%",
                    "riskValue": 2,
                    "chartTimeframe": "4H",
                },
                headers=headers,
            )
            assert tr_res.status_code == 201
            trade_id = tr_res.json()["id"]
            assert tr_res.json()["chartTimeframe"] == "15m"

            # Normal user cannot regenerate chart timeframe -> 403
            forbid_regen = await ac.post(
                f"/api/trades/{trade_id}/regenerate-chart",
                json={"timeframe": "1H"},
                headers=headers,
            )
            assert forbid_regen.status_code == 403

            # Step B: Admin reviews & approves payment, and edits VIP settings
            app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
                id=111111111, first_name="Admin", role="ADMIN"
            )
            pending_res = await ac.get("/api/admin/payments?status=PENDING", headers=headers)
            assert pending_res.status_code == 200
            assert any(p["id"] == payment_id for p in pending_res.json())

            app_res = await ac.post(f"/api/admin/payments/{payment_id}/approve", headers=headers)
            assert app_res.status_code == 200
            assert app_res.json()["userRole"] == "VIP"
            assert app_res.json()["subscriptionEndDate"] is not None

            # Manual VIP edit: add 10 days
            man_res = await ac.post(
                f"/api/admin/users/{test_uid}/vip",
                json={"action": "add_days", "days": 10},
                headers=headers,
            )
            assert man_res.status_code == 200
            assert man_res.json()["role"] == "VIP"

            # Step C: Now upgraded VIP user can regenerate chart to 1H
            app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
                id=test_uid, first_name="VipApplicant", role="USER"
            )
            vip_regen = await ac.post(
                f"/api/trades/{trade_id}/regenerate-chart",
                json={"timeframe": "1H"},
                headers=headers,
            )
            assert vip_regen.status_code == 200
            assert vip_regen.json()["chartTimeframe"] == "1H"
            assert vip_regen.json()["isCustomChart"] is False

        # Step D: Expired VIP auto-downgrades cleanly to USER
        async with AsyncSessionLocal() as session:
            u_repo = UserRepository(session)
            db_u = await u_repo.get_by_id(test_uid)
            db_u.subscription_end_date = datetime.now(timezone.utc) - timedelta(days=1)
            await session.commit()
            assert await u_repo.resolve_effective_role(db_u) == "USER"
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        async with AsyncSessionLocal() as session:
            await session.execute(delete(Payment).where(Payment.user_id == test_uid))
            await session.execute(delete(Trade).where(Trade.user_id == test_uid))
            await session.execute(delete(User).where(User.id == test_uid))
            await session.commit()


@pytest.mark.asyncio
async def test_idor_protection_on_alerts_and_trades(monkeypatch):
    """Verify users cannot mutate/delete another user's alerts or trades."""
    from app.api.deps import get_current_user
    from app.core.security import AuthenticatedUser
    from app.models.alert import PriceAlert
    from app.models.trade import Trade
    from app.models.user import User
    from app.repositories.alert_repo import AlertRepository
    from app.repositories.user_repo import UserRepository
    from app.services.market_service import MarketService
    from sqlalchemy import delete

    owner_id = 555001
    attacker_id = 555002

    async def fake_ohlcv(*args, **kwargs):
        return None

    monkeypatch.setattr(MarketService, "fetch_ohlcv_dataframe", fake_ohlcv)

    async with AsyncSessionLocal() as session:
        u_repo = UserRepository(session)
        await u_repo.get_or_create(telegram_id=owner_id, first_name="Owner", role="USER")
        await u_repo.get_or_create(telegram_id=attacker_id, first_name="Attacker", role="VIP")
        a_repo = AlertRepository(session)
        alert = await a_repo.create(
            PriceAlert(
                user_id=owner_id,
                symbol="BTC/USDT",
                alert_type="PRICE",
                base_price=62000.0,
                target_value=65000.0,
                trigger_price=65000.0,
                direction="UP",
            )
        )
        alert_id = alert.id

    headers = {"X-Telegram-Init-Data": "DEV_MOCK_USER"}
    try:
        # 1. Alert IDOR guard: attacker cannot delete owner's alert
        async with AsyncSessionLocal() as session:
            a_repo = AlertRepository(session)
            assert await a_repo.delete_by_id_and_user(alert_id, attacker_id) is False
            assert await a_repo.get_by_id(alert_id) is not None
            assert await a_repo.delete_by_id_and_user(alert_id, owner_id) is True

        # 2. Trade IDOR guard across PATCH / DELETE / regenerate-chart
        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
            id=owner_id, first_name="Owner", role="USER"
        )
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            create_res = await ac.post(
                "/api/trades",
                json={
                    "pair": "BTC / USDT",
                    "base": "BTC",
                    "isLong": True,
                    "entryPrice": 62100,
                    "stopLoss": 61900,
                    "takeProfit": 62500,
                    "leverage": 10,
                    "balance": 1000,
                    "riskType": "%",
                    "riskValue": 2,
                },
                headers=headers,
            )
            assert create_res.status_code == 201
            trade_id = create_res.json()["id"]

            app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
                id=attacker_id, first_name="Attacker", role="VIP"
            )
            patch_res = await ac.patch(f"/api/trades/{trade_id}", json={"status": "TP"}, headers=headers)
            assert patch_res.status_code == 404

            del_res = await ac.delete(f"/api/trades/{trade_id}", headers=headers)
            assert del_res.status_code == 404

            regen_res = await ac.post(
                f"/api/trades/{trade_id}/regenerate-chart",
                json={"timeframe": "1H"},
                headers=headers,
            )
            assert regen_res.status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        async with AsyncSessionLocal() as session:
            await session.execute(delete(PriceAlert).where(PriceAlert.user_id.in_([owner_id, attacker_id])))
            await session.execute(delete(Trade).where(Trade.user_id.in_([owner_id, attacker_id])))
            await session.execute(delete(User).where(User.id.in_([owner_id, attacker_id])))
            await session.commit()


def test_format_crypto_price_and_channel_url_parsing():
    """Verify smart crypto price formatting and Telegram t.me URL normalization."""
    from decimal import Decimal
    from types import SimpleNamespace
    from datetime import datetime, timezone
    from app.core.exceptions import BusinessValidationError
    from app.core.formatters import format_crypto_price
    from app.services.channel_service import ChannelService

    assert format_crypto_price(60000.9200000) == "60000.92"
    assert format_crypto_price(Decimal("60000.00000000")) == "60000"
    assert format_crypto_price(1.23456) == "1.2346"
    assert format_crypto_price(0.00002000) == "0.00002"
    assert format_crypto_price(2e-05) == "0.00002"
    assert format_crypto_price(1e-08) == "0.00000001"
    assert format_crypto_price(0.0) == "0"
    assert format_crypto_price(None) == "—"

    assert ChannelService.parse_channel_identifier("https://t.me/To_Be_complete") == "@To_Be_complete"
    assert ChannelService.parse_channel_identifier("t.me/To_Be_complete/") == "@To_Be_complete"
    assert ChannelService.parse_channel_identifier("http://t.me/To_Be_complete?single") == "@To_Be_complete"
    assert ChannelService.parse_channel_identifier("@To_Be_complete") == "@To_Be_complete"
    assert ChannelService.parse_channel_identifier("To_Be_complete") == "@To_Be_complete"
    assert ChannelService.parse_channel_identifier("-1001987654321") == -1001987654321
    with pytest.raises(BusinessValidationError):
        ChannelService.parse_channel_identifier("https://t.me/+privateInvite123")

    mock_trade = SimpleNamespace(
        id="tr-fmt-1",
        pair="PEPE / USDT",
        symbol="PEPEUSDT",
        base_asset="PEPE",
        is_long=True,
        entry_price=Decimal("0.00002000"),
        stop_loss=Decimal("0.00001800"),
        take_profit=Decimal("0.00002500"),
        position_size=Decimal("1000000"),
        required_margin=Decimal("2.00"),
        leverage=10,
        risk_amount=Decimal("2.00"),
        potential_profit=Decimal("5.00"),
        rr_ratio=Decimal("2.50"),
        status="OPEN",
        realized_pnl=Decimal("0.00"),
        strategy_name="Breakout",
        entry_reason="",
        notes="",
        created_at=datetime.now(timezone.utc),
        has_chart_snapshot=True,
        chart_timeframe="15m",
        chart_image_url=None,
        is_custom_chart=False,
        telegram_message_id=None,
    )
    rendered = ChannelService.render_caption(
        mock_trade,
        template_str="E={{ entry_price }}|SL={{ sl }}|TP={{ tp }}",
    )
    assert rendered == "E=0.00002|SL=0.000018|TP=0.000025"


@pytest.mark.asyncio
async def test_initial_chart_uses_same_unified_addplot_renderer(monkeypatch):
    """Verify initial POST /api/v1/trades and regenerate-chart both render Entry/SL/TP lines via unified pipeline."""
    from unittest.mock import AsyncMock
    import pandas as pd
    from sqlalchemy import delete
    from app.api.deps import get_current_user
    from app.core.security import AuthenticatedUser
    from app.models.trade import Trade
    from app.models.user import User
    from app.repositories.user_repo import UserRepository
    from app.services.chart_service import ChartService
    from app.services.market_service import MarketService

    uid = 555099
    idx = pd.date_range("2026-01-01", periods=20, freq="15min")
    sample_df = pd.DataFrame(
        {"open": [60000.0] * 20, "high": [60150.0] * 20, "low": [59850.0] * 20, "close": [60050.0] * 20, "volume": [100.0] * 20},
        index=idx,
    )
    monkeypatch.setattr(MarketService, "fetch_ohlcv_dataframe", AsyncMock(return_value=sample_df))

    render_calls = []
    orig_render = ChartService._render_mplfinance_bytes_sync

    def spy_render(df, entry, sl, tp, symbol, timeframe):
        render_calls.append((float(entry), float(sl) if sl else None, float(tp) if tp else None, timeframe))
        return orig_render(df, entry, sl, tp, symbol, timeframe)

    monkeypatch.setattr(ChartService, "_render_mplfinance_bytes_sync", spy_render)

    async with AsyncSessionLocal() as session:
        await UserRepository(session).get_or_create(telegram_id=uid, first_name="ChartTester", role="VIP")

    headers = {"X-Telegram-Init-Data": "DEV_MOCK_USER"}
    trade_id = None
    try:
        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
            id=uid, first_name="ChartTester", role="VIP"
        )
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res = await ac.post(
                "/api/v1/trades",
                json={
                    "pair": "BTC / USDT",
                    "base": "BTC",
                    "isLong": True,
                    "entryPrice": "60000.9200000",
                    "stopLoss": "59700.00",
                    "takeProfit": "60500.50",
                    "leverage": 10,
                    "balance": 1000,
                    "riskType": "%",
                    "riskValue": 2,
                },
                headers=headers,
            )
            assert res.status_code == 201
            trade_id = res.json()["id"]
            assert res.json()["entryPrice"] == "60000.92"
            assert res.json()["chartTimeframe"] == "15m"
            assert res.json()["customChartUrl"] == f"/static/charts_auto/{trade_id}_15m.png"
            assert len(render_calls) == 1

            regen = await ac.post(
                f"/api/v1/trades/{trade_id}/regenerate-chart",
                json={"timeframe": "15m"},
                headers=headers,
            )
            assert regen.status_code == 200
            assert len(render_calls) == 2
            assert render_calls[0] == render_calls[1] == (60000.92, 59700.0, 60500.5, "15m")
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        if trade_id:
            ChartService.remove_chart_file(f"/static/charts_auto/{trade_id}_15m.png")
        async with AsyncSessionLocal() as session:
            await session.execute(delete(Trade).where(Trade.user_id == uid))
            await session.execute(delete(User).where(User.id == uid))
            await session.commit()


@pytest.mark.asyncio
async def test_superchart_klines_vip_gating_and_failsafe_503(monkeypatch):
    """Verify /api/v1/market/klines rejects USER and expired VIP with 403, and returns 503 + admin alert on exchange errors."""
    import asyncio
    from datetime import datetime, timedelta, timezone
    from unittest.mock import AsyncMock
    from sqlalchemy import delete
    from app.api.deps import get_current_user
    from app.api.v1 import market as market_router_mod
    from app.core.security import AuthenticatedUser
    from app.models.user import User
    from app.repositories.user_repo import UserRepository
    from app.services.market_service import MarketService

    uid_user = 555201
    uid_vip = 555202

    async with AsyncSessionLocal() as session:
        repo = UserRepository(session)
        await repo.get_or_create(telegram_id=uid_user, first_name="FreeUser", role="USER")
        vip = await repo.get_or_create(telegram_id=uid_vip, first_name="VipUser", role="VIP")
        await repo.update_vip_subscription(
            vip, role="VIP", subscription_end_date=datetime.now(timezone.utc) + timedelta(days=10)
        )

    headers = {"X-Telegram-Init-Data": "DEV_MOCK_USER"}
    alert_calls = []

    async def fake_notify(err_details: str, symbol: str, timeframe: str):
        alert_calls.append((err_details, symbol, timeframe))

    monkeypatch.setattr(market_router_mod, "_notify_admin_exchange_error", fake_notify)

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # 1. Free USER blocked -> 403
            app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
                id=uid_user, first_name="FreeUser", role="USER"
            )
            r_free = await ac.get("/api/v1/market/klines?symbol=BTCUSDT&timeframe=15m", headers=headers)
            assert r_free.status_code == 403

            # 2. Active VIP succeeds -> 200
            sample_bars = [
                {"timestamp": 1700000000000 + i * 900000, "open": 60000.0, "high": 60100.0, "low": 59900.0, "close": 60050.0, "volume": 12.5}
                for i in range(25)
            ]
            monkeypatch.setattr(MarketService, "fetch_live_ohlcv_strict", AsyncMock(return_value=sample_bars))
            app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
                id=uid_vip, first_name="VipUser", role="USER"
            )
            r_vip = await ac.get("/api/v1/market/klines?symbol=BTCUSDT&timeframe=15m", headers=headers)
            assert r_vip.status_code == 200
            assert len(r_vip.json()["bars"]) == 25
            assert r_vip.json()["hasMore"] is False

            # 2.5 Historical pagination via before_timestamp
            hist_mock = AsyncMock(return_value=sample_bars[:5])
            monkeypatch.setattr(MarketService, "fetch_live_ohlcv_strict", hist_mock)
            r_hist = await ac.get(
                "/api/v1/market/klines?symbol=BTCUSDT&timeframe=15m&limit=20&before_timestamp=1700004500000",
                headers=headers,
            )
            assert r_hist.status_code == 200
            assert hist_mock.call_args.kwargs["before_timestamp"] == 1700004500000

            # 3. Exchange failure -> async admin alert + 503
            monkeypatch.setattr(
                MarketService,
                "fetch_live_ohlcv_strict",
                AsyncMock(side_effect=TimeoutError("Binance timeout")),
            )
            r_err = await ac.get("/api/v1/market/klines?symbol=BTCUSDT&timeframe=15m", headers=headers)
            assert r_err.status_code == 503
            await asyncio.sleep(0)
            assert len(alert_calls) == 1
            assert "Binance timeout" in alert_calls[0][0]

            # 4. Expired VIP blocked -> 403
            async with AsyncSessionLocal() as session:
                repo = UserRepository(session)
                vip_row = await repo.get_by_id(uid_vip)
                await repo.update_vip_subscription(
                    vip_row, role="VIP", subscription_end_date=datetime.now(timezone.utc) - timedelta(minutes=5)
                )
            r_exp = await ac.get("/api/v1/market/klines?symbol=BTCUSDT&timeframe=15m", headers=headers)
            assert r_exp.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        async with AsyncSessionLocal() as session:
            await session.execute(delete(User).where(User.id.in_([uid_user, uid_vip])))
            await session.commit()


def test_superchart_websocket_stream_vip_gating_and_push(monkeypatch):
    """Verify WebSocket /api/v1/market/stream rejects non-VIPs and pushes live candle frames to VIP/ADMIN."""
    from unittest.mock import AsyncMock
    from fastapi.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect
    from app.core.security import AuthenticatedUser
    from app.api.v1 import market as market_router_mod
    from app.services.market_service import MarketService

    live_bar = [
        {"timestamp": 1700000900000, "open": 60100.0, "high": 60250.0, "low": 60050.0, "close": 60210.0, "volume": 19.4}
    ]
    monkeypatch.setattr(MarketService, "fetch_live_ohlcv_strict", AsyncMock(return_value=live_bar))

    # 1. Normal USER denied (4403 close)
    monkeypatch.setattr(
        market_router_mod,
        "verify_telegram_init_data",
        lambda _raw: AuthenticatedUser(id=555299, first_name="Free", role="USER"),
    )
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect("/api/v1/market/stream?symbol=BTCUSDT&timeframe=15m&init_data=TEST"):
                pass
        assert exc_info.value.code == 4403

        # 2. ADMIN/VIP receives live kline frame immediately
        monkeypatch.setattr(
            market_router_mod,
            "verify_telegram_init_data",
            lambda _raw: AuthenticatedUser(id=111111111, first_name="Admin", role="ADMIN"),
        )
        with client.websocket_connect("/api/v1/market/stream?symbol=BTCUSDT&timeframe=15m&init_data=TEST") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "kline"
            assert msg["bar"]["close"] == 60210.0
