from typing import Generic, TypeVar, Optional, Any
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

DataT = TypeVar("DataT")


class CamelModel(BaseModel):
    """Base Pydantic model with automatic camelCase alias generator and ORM mode."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True
    )


class ApiResponse(CamelModel, Generic[DataT]):
    """Standard unified API envelope."""

    success: bool = True
    message: str = "عملیات با موفقیت انجام شد"
    data: Optional[DataT] = None
