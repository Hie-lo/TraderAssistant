import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database.session import AsyncSessionLocal
from app.database.seed import seed_initial_settings
from app.core.dynamic_config import DynamicConfig


@pytest.fixture(autouse=True)
async def setup_test_db():
    from app.database.session import engine
    from app.models.base import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

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
