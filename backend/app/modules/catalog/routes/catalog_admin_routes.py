from math import ceil
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, get_db
from app.core.admin import require_admin
from app.models.audit_log_event import AuditLogEvent
from app.modules.catalog.schemas.catalog_admin import (
    CatalogAdminCategory,
    CatalogAdminItemCard,
    CatalogAdminItemDetails,
    CatalogAdminItemImage,
    CatalogAdminItemsResponse,
    CatalogAdminOwner,
)
from app.modules.items.models.item import Item
from app.modules.users.models.user import User
from app.services.image_url import build_versioned_image_url

router = APIRouter()


ITEM_STATUSES = {
    "draft",
    "pending_review",
    "published",
    "rejected",
}

SORT_VALUES = {
    "newest",
    "oldest",
    "updated_desc",
    "updated_asc",
    "price_asc",
    "price_desc",
    "title_asc",
    "title_desc",
}


def _write_catalog_view_audit(
    db: Session,
    *,
    actor_user_id: UUID,
    action: str,
    meta: dict,
) -> None:
    db.add(
        AuditLogEvent(
            actor_user_id=actor_user_id,
            action=action,
            entity_type="Catalog",
            entity_id=None,
            meta=meta,
        )
    )


def _serialize_admin_image(image) -> CatalogAdminItemImage:
    return CatalogAdminItemImage(
        id=image.id,
        url=image.url,
        versioned_url=build_versioned_image_url(image.url, image.version),
        storage_path=image.storage_path,
        mime_type=image.mime_type,
        file_size_bytes=image.file_size_bytes,
        sort_order=image.sort_order,
        version=image.version,
        created_at=image.created_at,
    )


def _serialize_admin_item_card(item: Item) -> CatalogAdminItemCard:
    preview_image_url = None

    if item.images:
        preview_image_url = build_versioned_image_url(
            item.images[0].url,
            item.images[0].version,
        )

    return CatalogAdminItemCard(
        id=item.id,
        owner_id=item.owner_id,
        owner_email=item.owner.email if item.owner else None,
        owner_name=item.owner.full_name if item.owner else None,
        category_id=item.category_id,
        category_name=item.category.name if item.category else None,
        title=item.title,
        description=item.description,
        city=item.city,
        pickup_address=item.pickup_address,
        status=item.status,
        daily_price_cents=item.daily_price_cents,
        deposit_cents=item.deposit_cents,
        images_count=len(item.images or []),
        preview_image_url=preview_image_url,
        moderated_by=item.moderated_by,
        moderated_at=item.moderated_at,
        moderation_comment=item.moderation_comment,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _serialize_admin_item_details(item: Item) -> CatalogAdminItemDetails:
    return CatalogAdminItemDetails(
        id=item.id,
        owner_id=item.owner_id,
        category_id=item.category_id,
        title=item.title,
        description=item.description,
        city=item.city,
        pickup_address=item.pickup_address,
        status=item.status,
        daily_price_cents=item.daily_price_cents,
        deposit_cents=item.deposit_cents,
        moderated_by=item.moderated_by,
        moderated_at=item.moderated_at,
        moderation_comment=item.moderation_comment,
        created_at=item.created_at,
        updated_at=item.updated_at,
        owner=CatalogAdminOwner(
            id=item.owner.id if item.owner else None,
            email=item.owner.email if item.owner else None,
            full_name=item.owner.full_name if item.owner else None,
            city=item.owner.city if item.owner else None,
            is_active=item.owner.is_active if item.owner else None,
            email_verified=item.owner.email_verified if item.owner else None,
        )
        if item.owner
        else None,
        category=CatalogAdminCategory(
            id=item.category.id if item.category else None,
            name=item.category.name if item.category else None,
        )
        if item.category
        else None,
        images=[_serialize_admin_image(image) for image in item.images],
    )


def _apply_sort(query, sort: str):
    if sort == "newest":
        return query.order_by(Item.created_at.desc())

    if sort == "oldest":
        return query.order_by(Item.created_at.asc())

    if sort == "updated_desc":
        return query.order_by(Item.updated_at.desc())

    if sort == "updated_asc":
        return query.order_by(Item.updated_at.asc())

    if sort == "price_asc":
        return query.order_by(Item.daily_price_cents.asc(), Item.created_at.desc())

    if sort == "price_desc":
        return query.order_by(Item.daily_price_cents.desc(), Item.created_at.desc())

    if sort == "title_asc":
        return query.order_by(Item.title.asc())

    if sort == "title_desc":
        return query.order_by(Item.title.desc())

    return query.order_by(Item.updated_at.desc())


@router.get("/admin/items", response_model=CatalogAdminItemsResponse)
def read_catalog_items_as_admin(
    status: str | None = Query(default=None),
    owner_id: UUID | None = Query(default=None),
    category_id: UUID | None = Query(default=None),
    city: str | None = Query(default=None),
    title: str | None = Query(default=None),
    description: str | None = Query(default=None),
    search: str | None = Query(default=None),
    price_from: int | None = Query(default=None, ge=0),
    price_to: int | None = Query(default=None, ge=0),
    sort: str = Query(default="updated_desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    write_audit: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    if status and status not in ITEM_STATUSES:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Unsupported item status",
                "allowed_statuses": sorted(ITEM_STATUSES),
            },
        )

    if sort not in SORT_VALUES:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Unsupported sort value",
                "allowed_sort_values": sorted(SORT_VALUES),
            },
        )

    base_query = db.query(Item)

    if status:
        base_query = base_query.filter(Item.status == status)

    if owner_id:
        base_query = base_query.filter(Item.owner_id == owner_id)

    if category_id:
        base_query = base_query.filter(Item.category_id == category_id)

    if city:
        base_query = base_query.filter(Item.city.ilike(f"%{city.strip()}%"))

    if title:
        base_query = base_query.filter(Item.title.ilike(f"%{title.strip()}%"))

    if description:
        base_query = base_query.filter(Item.description.ilike(f"%{description.strip()}%"))

    if search:
        search_value = f"%{search.strip()}%"
        base_query = base_query.filter(
            or_(
                Item.title.ilike(search_value),
                Item.description.ilike(search_value),
                Item.city.ilike(search_value),
            )
        )

    if price_from is not None:
        base_query = base_query.filter(Item.daily_price_cents >= price_from)

    if price_to is not None:
        base_query = base_query.filter(Item.daily_price_cents <= price_to)

    total = base_query.count()
    pages = ceil(total / page_size) if total > 0 else 1
    offset = (page - 1) * page_size

    query = base_query.options(
        selectinload(Item.images),
        selectinload(Item.category),
        selectinload(Item.owner),
    )

    query = _apply_sort(query, sort)

    items = query.offset(offset).limit(page_size).all()

    if write_audit:
        _write_catalog_view_audit(
            db,
            actor_user_id=current_user.id,
            action="catalog.admin_search",
            meta={
                "status": status,
                "owner_id": str(owner_id) if owner_id else None,
                "category_id": str(category_id) if category_id else None,
                "city": city,
                "title": title,
                "description": description,
                "search": search,
                "price_from": price_from,
                "price_to": price_to,
                "sort": sort,
                "page": page,
                "page_size": page_size,
                "total": total,
            },
        )
        db.commit()

    return CatalogAdminItemsResponse(
        items=[_serialize_admin_item_card(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
        pages=pages,
    )


@router.get("/admin/items/{item_id}", response_model=CatalogAdminItemDetails)
def read_catalog_item_details_as_admin(
    item_id: UUID,
    write_audit: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    item = (
        db.query(Item)
        .options(
            selectinload(Item.images),
            selectinload(Item.category),
            selectinload(Item.owner),
        )
        .filter(Item.id == item_id)
        .first()
    )

    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    if write_audit:
        _write_catalog_view_audit(
            db,
            actor_user_id=current_user.id,
            action="catalog.admin_read_item",
            meta={
                "item_id": str(item.id),
                "status": item.status,
                "owner_id": str(item.owner_id),
                "category_id": str(item.category_id),
            },
        )
        db.commit()

    return _serialize_admin_item_details(item)