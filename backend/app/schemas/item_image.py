from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ItemImageRead(BaseModel):
    id: UUID
    item_id: UUID
    url: str
    versioned_url: str
    storage_path: str
    mime_type: str | None = None
    file_size_bytes: int | None = None
    sort_order: int
    version: int
    created_at: datetime

    model_config = {"from_attributes": True}