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
