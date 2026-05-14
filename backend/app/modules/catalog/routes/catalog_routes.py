from math import ceil
from uuid import UUID

import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_db
from app.core.config import settings
from app.models.item import Item
from app.schemas.catalog import (
    CatalogItemCard,
    CatalogItemDetails,
    CatalogItemImagePublic,
    CatalogItemsResponse,
    CatalogOwnerPublic,
)
from app.services.cache import cache_service
from app.services.cache_keys import (
    catalog_item_details_key,
    catalog_search_key,
    catalog_search_namespace,
)
from app.services.etag import build_etag
from app.services.image_url import build_versioned_image_url

router = APIRouter()
logger = logging.getLogger(__name__)


def _build_catalog_item_card(item: Item) -> CatalogItemCard:
    preview_image = build_versioned_image_url(item.images[0].url, item.images[0].version) if item.images else None

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
                versioned_url=build_versioned_image_url(image.url, image.version),
                sort_order=image.sort_order,
                version=image.version,
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

    namespace_version = cache_service.get_namespace_version(catalog_search_namespace())
    cache_key = catalog_search_key(
        namespace_version=namespace_version,
        city=city,
        category_id=category_id,
        price_from=price_from,
        price_to=price_to,
        page=page,
        page_size=page_size,
        sort=sort,
    )

    cached_payload = cache_service.get_json(cache_key)
    if cached_payload is not None:
        logger.info(
            "Catalog search cache hit (v%s) for key=%s",
            namespace_version,
            cache_key,
        )
        return CatalogItemsResponse.model_validate(cached_payload)

    logger.info(
        "Catalog search cache miss (v%s) for key=%s",
        namespace_version,
        cache_key,
    )

    base_query = db.query(Item).filter(Item.status == "published")

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

    response_payload = CatalogItemsResponse(
        items=[_build_catalog_item_card(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
        pages=pages,
    ).model_dump(mode="json")

    cache_service.set_json(
        key=cache_key,
        value=response_payload,
        ttl_seconds=settings.CACHE_TTL_CATALOG_SEARCH_SECONDS,
    )

    return CatalogItemsResponse.model_validate(response_payload)


@router.get("/items/{item_id}", response_model=CatalogItemDetails)
def read_catalog_item_details(
    item_id: UUID,
    response: Response,
    db: Session = Depends(get_db),
    if_none_match: str | None = Header(default=None),
) -> CatalogItemDetails | Response:
    cache_key = catalog_item_details_key(str(item_id))

    cached_payload = cache_service.get_json(cache_key)
    if cached_payload is not None:
        logger.info("Catalog item details cache hit for item_id=%s", item_id)
        response_payload = cached_payload
    else:
        logger.info("Catalog item details cache miss for item_id=%s", item_id)

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

        response_payload = _build_catalog_item_details(item).model_dump(mode="json")

        cache_service.set_json(
            key=cache_key,
            value=response_payload,
            ttl_seconds=settings.CACHE_TTL_ITEM_DETAILS_SECONDS,
        )

    etag = build_etag(response_payload)

    if if_none_match == etag:
        logger.info("Catalog item details ETag match -> 304 for item_id=%s", item_id)
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers={"ETag": etag})

    response.headers["ETag"] = etag
    return CatalogItemDetails.model_validate(response_payload)