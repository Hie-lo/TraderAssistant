from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.core.security import AuthenticatedUser
from app.core.dynamic_config import DynamicConfig
from app.repositories.user_repo import UserRepository
from app.repositories.strategy_repo import StrategyRepository
from app.repositories.trade_repo import TradeRepository
from app.services.trade_service import TradeService
from app.services.pair_service import PairService
from app.services.subscription_service import SubscriptionService
from app.schemas.dashboard_schema import (
    BootstrapResponseSchema,
    UserProfileSchema,
    DynamicAppConfigSchema,
    ConfigPairSchema
)

router = APIRouter(tags=["Bootstrap"])


@router.get("/bootstrap", response_model=BootstrapResponseSchema)
async def get_initial_bootstrap(
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Unified bootstrap endpoint called upon Mini-App load.
    Returns user profile, dynamic settings, pairs, user strategies, and full trade history.
    """
    user_repo = UserRepository(db)
    strategy_repo = StrategyRepository(db)
    trade_repo = TradeRepository(db)

    # 1. Fetch or create user record
    db_user = await user_repo.get_or_create(
        telegram_id=current_user.id,
        first_name=current_user.first_name,
        username=current_user.username,
        role=current_user.role
    )

    # 2. Fetch custom user strategies
    user_strats = await strategy_repo.get_by_user(current_user.id)
    custom_strategies_list = [s.name for s in user_strats]
    if not custom_strategies_list and current_user.is_mock:
        custom_strategies_list = ["ستاپ شخصی فیبوناچی"]

    # 3. Fetch trade journal
    db_trades = await trade_repo.list_by_user(current_user.id, limit=200)
    formatted_trades = [TradeService.trade_to_response(t) for t in db_trades]

    # 4. Construct configuration
    pairs_data = DynamicConfig.get("supported_pairs", [])
    config_pairs = [
        ConfigPairSchema(
            symbol=p["symbol"],
            label=p["label"],
            base=p["base"],
            icon=p["icon"],
            color=p["color"],
            default_price=str(p["defaultPrice"]),
            step=float(p["step"])
        )
        for p in pairs_data
    ]

    default_strats = DynamicConfig.get("default_strategies", [])

    effective_role = await user_repo.resolve_effective_role(db_user)
    return BootstrapResponseSchema(
        user=UserProfileSchema(
            id=db_user.id,
            first_name=db_user.first_name,
            default_balance=f"{db_user.default_balance:.2f}",
            discipline_badge="سطح انضباط: حرفه‌ای 🛡️",
            status=db_user.status,
            role="ADMIN" if current_user.role == "ADMIN" else effective_role,
            subscription_end_date=(
                db_user.subscription_end_date.isoformat() if db_user.subscription_end_date else None
            ),
            photo_url=current_user.photo_url
        ),
        config=DynamicAppConfigSchema(
            max_leverage=int(DynamicConfig.get("max_leverage", 2000)),
            pairs=config_pairs,
            default_strategies=default_strats
        ),
        custom_strategies=custom_strategies_list,
        trades=formatted_trades,
        vip_config=SubscriptionService.get_vip_public_config()
    )


@router.get("/pairs")
async def get_unified_active_pairs(
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """Returns the centralized active exchange pairs list shared with the Telegram bot."""
    return await PairService.get_active_pairs()
