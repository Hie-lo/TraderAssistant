from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.core.security import AuthenticatedUser
from app.core.dynamic_config import DynamicConfig
from app.models.strategy import UserStrategy
from app.repositories.strategy_repo import StrategyRepository
from app.schemas.strategy_schema import StrategyCreateSchema, StrategyResponseSchema
from app.schemas.common import ApiResponse
from app.core.exceptions import BusinessValidationError, NotFoundError

router = APIRouter(prefix="/strategies", tags=["Strategies"])


@router.post("", response_model=StrategyResponseSchema, status_code=201)
async def create_user_strategy(
    strategy_in: StrategyCreateSchema,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Adds a new custom trading strategy for the user."""
    name = strategy_in.name.strip()
    if not name:
        raise BusinessValidationError("نام استراتژی نمی‌تواند خالی باشد.")

    strat_repo = StrategyRepository(db)
    existing = await strat_repo.get_by_user_and_name(current_user.id, name)
    if existing:
        return StrategyResponseSchema(id=existing.id, name=existing.name)

    new_strat = UserStrategy(user_id=current_user.id, name=name)
    saved = await strat_repo.create(new_strat)
    return StrategyResponseSchema(id=saved.id, name=saved.name)


@router.delete("/{strategy_name}")
async def delete_user_strategy(
    strategy_name: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Deletes a personal strategy and reassigns any associated trades to the default strategy."""
    strat_repo = StrategyRepository(db)
    deleted = await strat_repo.delete_by_user_and_name(current_user.id, strategy_name)
    if not deleted:
        raise NotFoundError("استراتژی شخصی با این نام یافت نشد.")

    default_strats = DynamicConfig.get("default_strategies", ["Price Action"])
    fallback_strategy = default_strats[0] if default_strats else "Price Action"

    reassigned_count = await strat_repo.reassign_trades_strategy(
        user_id=current_user.id,
        old_strategy=strategy_name,
        new_strategy=fallback_strategy
    )

    return {
        "success": True,
        "message": f"استراتژی '{strategy_name}' با موفقیت حذف شد.",
        "reassignedTrades": reassigned_count
    }
