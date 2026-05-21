from pydantic import BaseModel, Field


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class CategoryUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=255)