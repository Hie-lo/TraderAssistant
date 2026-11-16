from app.schemas.common import CamelModel


class StrategyCreateSchema(CamelModel):
    """Schema for adding a new personal user strategy."""
    name: str


class StrategyResponseSchema(CamelModel):
    """Schema for returning user strategy."""
    id: int
    name: str
