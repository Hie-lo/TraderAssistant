from fastapi import APIRouter
from app.api.v1.bootstrap import router as bootstrap_router
from app.api.v1.trades import router as trades_router
from app.api.v1.strategies import router as strategies_router
from app.api.v1.admin import router as admin_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(bootstrap_router)
api_v1_router.include_router(trades_router)
api_v1_router.include_router(strategies_router)
api_v1_router.include_router(admin_router)
