from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.item_image import ItemImageRead


class ItemBase(BaseModel):
    category_id: UUID
    title: str = Field(min_length=3, max_length=255)
    description: str = Field(min_length=10, max_length=5000)
    daily_price_cents: int = Field(ge=0)
    deposit_cents: int = Field(ge=0)
    city: str = Field(min_length=2, max_length=120)
    pickup_address: str = Field(min_length=5, max_length=255)


class ItemCreate(ItemBase):
    pass


class ItemUpdate(ItemBase):
    pass


class ItemRead(ItemBase):
    id: UUID
    owner_id: UUID
    status: str
    created_at: datetime
    updated_at: datetime
    images: list[ItemImageRead] = []

    model_config = {'from_attributes': True}
