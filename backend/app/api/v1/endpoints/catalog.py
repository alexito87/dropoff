from math import ceil
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_db
from app.models.item import Item
from app.schemas.catalog import (
    CatalogItemCard,
    CatalogItemDetails,
    CatalogItemImagePublic,
    CatalogItemsResponse,
    CatalogOwnerPublic,
)

router = APIRouter()


def _build_catalog_item_card(item: Item) -> CatalogItemCard:
    preview_image = item.images[0].url if item.images else None

    return CatalogItemCard(
        id=item.id,
        title=item.title,
        city=item.city,
        daily_price_cents=item.daily_price_cents,
        deposit_cents=item.deposit_cents,
        category_id=item.category_id,
        category_name=item.category.name if item.category else "",
        preview_image_url=preview_image,
        created_at=item.created_at,
    )


def _build_catalog_item_details(item: Item) -> CatalogItemDetails:
    return CatalogItemDetails(
        id=item.id,
        title=item.title,
        description=item.description,
        city=item.city,
        daily_price_cents=item.daily_price_cents,
        deposit_cents=item.deposit_cents,
        category_id=item.category_id,
        category_name=item.category.name if item.category else "",
        images=[
            CatalogItemImagePublic(
                id=image.id,
                url=image.url,
                sort_order=image.sort_order,
            )
            for image in item.images
        ],
        owner=CatalogOwnerPublic(
            id=item.owner.id if item.owner else None,
            full_name=item.owner.full_name if item.owner else None,
            city=item.owner.city if item.owner else None,
        ),
    )


@router.get("/items", response_model=CatalogItemsResponse)
def read_catalog_items(
    city: str | None = Query(default=None),
    category_id: UUID | None = Query(default=None),
    price_from: int | None = Query(default=None, ge=0),
    price_to: int | None = Query(default=None, ge=0),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=12, ge=1, le=50),
    sort: str = Query(default="newest"),
    db: Session = Depends(get_db),
):
    if sort not in {"newest", "price_asc", "price_desc"}:
        raise HTTPException(
            status_code=400,
            detail="Unsupported sort value. Allowed: newest, price_asc, price_desc",
        )

    base_query = (
        db.query(Item)
        .filter(Item.status == "published")
    )

    if city:
        base_query = base_query.filter(func.lower(Item.city) == city.strip().lower())

    if category_id:
        base_query = base_query.filter(Item.category_id == category_id)

    if price_from is not None:
        base_query = base_query.filter(Item.daily_price_cents >= price_from)

    if price_to is not None:
        base_query = base_query.filter(Item.daily_price_cents <= price_to)

    total = base_query.count()

    query = base_query.options(
        selectinload(Item.images),
        selectinload(Item.category),
    )

    if sort == "newest":
        query = query.order_by(Item.created_at.desc())
    elif sort == "price_asc":
        query = query.order_by(Item.daily_price_cents.asc(), Item.created_at.desc())
    elif sort == "price_desc":
        query = query.order_by(Item.daily_price_cents.desc(), Item.created_at.desc())

    offset = (page - 1) * page_size
    items = query.offset(offset).limit(page_size).all()

    pages = ceil(total / page_size) if total > 0 else 1

    return CatalogItemsResponse(
        items=[_build_catalog_item_card(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
        pages=pages,
    )


@router.get("/items/{item_id}", response_model=CatalogItemDetails)
def read_catalog_item_details(item_id: UUID, db: Session = Depends(get_db)):
    item = (
        db.query(Item)
        .options(
            selectinload(Item.images),
            selectinload(Item.category),
            selectinload(Item.owner),
        )
        .filter(Item.id == item_id, Item.status == "published")
        .first()
    )

    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    return _build_catalog_item_details(item)