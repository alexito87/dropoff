from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_admin, get_db
from app.models.item import Item
from app.models.notification import Notification
from app.models.user import User
from app.schemas.item import ItemRead
from app.schemas.item_image import ItemImageRead
from app.services.cache_invalidation import invalidate_public_catalog_for_item
from app.services.image_url import build_versioned_image_url

router = APIRouter()


class ModerationDecisionPayload(BaseModel):
    comment: str | None = Field(default=None, max_length=2000)


def _serialize_item_image(image) -> ItemImageRead:
    return ItemImageRead(
        id=image.id,
        item_id=image.item_id,
        url=image.url,
        versioned_url=build_versioned_image_url(image.url, image.version),
        storage_path=image.storage_path,
        mime_type=image.mime_type,
        file_size_bytes=image.file_size_bytes,
        sort_order=image.sort_order,
        version=image.version,
        created_at=image.created_at,
    )


def _serialize_item(item: Item) -> ItemRead:
    return ItemRead(
        id=item.id,
        owner_id=item.owner_id,
        category_id=item.category_id,
        title=item.title,
        description=item.description,
        daily_price_cents=item.daily_price_cents,
        deposit_cents=item.deposit_cents,
        city=item.city,
        pickup_address=item.pickup_address,
        status=item.status,
        moderated_by=item.moderated_by,
        moderated_at=item.moderated_at,
        moderation_comment=item.moderation_comment,
        created_at=item.created_at,
        updated_at=item.updated_at,
        images=[_serialize_item_image(image) for image in item.images],
    )


def _get_item_for_moderation(db: Session, item_id: UUID) -> Item:
    item = (
        db.query(Item)
        .options(selectinload(Item.images))
        .filter(Item.id == item_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


def _notify_owner(db: Session, item: Item, notification_type: str, comment: str | None):
    notification = Notification(
        user_id=item.owner_id,
        type=notification_type,
        payload={
            "item_id": str(item.id),
            "title": item.title,
            "status": item.status,
            "comment": comment,
        },
    )
    db.add(notification)


@router.get("/items", response_model=list[ItemRead])
def read_items_for_moderation(
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    items = (
        db.query(Item)
        .options(selectinload(Item.images))
        .filter(Item.status == "pending_review")
        .order_by(Item.created_at.asc())
        .all()
    )
    return [_serialize_item(item) for item in items]


@router.get("/items/{item_id}", response_model=ItemRead)
def read_item_for_moderation(
    item_id: UUID,
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return _serialize_item(_get_item_for_moderation(db, item_id))


@router.post("/items/{item_id}/approve", response_model=ItemRead)
def approve_item(
    item_id: UUID,
    payload: ModerationDecisionPayload,
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    item = _get_item_for_moderation(db, item_id)

    if item.status != "pending_review":
        raise HTTPException(status_code=400, detail="Only pending_review item can be approved")

    item.status = "published"
    item.moderated_by = admin_user.id
    item.moderated_at = datetime.now(timezone.utc)
    item.moderation_comment = payload.comment

    _notify_owner(db, item, "item_approved", payload.comment)

    db.add(item)
    db.commit()
    invalidate_public_catalog_for_item(item.id)
    db.refresh(item)
    return _serialize_item(item)


@router.post("/items/{item_id}/reject", response_model=ItemRead)
def reject_item(
    item_id: UUID,
    payload: ModerationDecisionPayload,
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    item = _get_item_for_moderation(db, item_id)

    if item.status != "pending_review":
        raise HTTPException(status_code=400, detail="Only pending_review item can be rejected")

    if not payload.comment:
        raise HTTPException(status_code=400, detail="Comment is required for reject")

    item.status = "rejected"
    item.moderated_by = admin_user.id
    item.moderated_at = datetime.now(timezone.utc)
    item.moderation_comment = payload.comment

    _notify_owner(db, item, "item_rejected", payload.comment)

    db.add(item)
    db.commit()
    invalidate_public_catalog_for_item(item.id)
    db.refresh(item)
    return _serialize_item(item)


@router.post("/items/{item_id}/needs-changes", response_model=ItemRead)
def needs_changes_item(
    item_id: UUID,
    payload: ModerationDecisionPayload,
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    item = _get_item_for_moderation(db, item_id)

    if item.status != "pending_review":
        raise HTTPException(status_code=400, detail="Only pending_review item can be sent to changes")

    if not payload.comment:
        raise HTTPException(status_code=400, detail="Comment is required for needs changes")

    item.status = "rejected"
    item.moderated_by = admin_user.id
    item.moderated_at = datetime.now(timezone.utc)
    item.moderation_comment = payload.comment

    _notify_owner(db, item, "item_needs_changes", payload.comment)

    db.add(item)
    db.commit()
    invalidate_public_catalog_for_item(item.id)
    db.refresh(item)
    return _serialize_item(item)