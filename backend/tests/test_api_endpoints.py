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
