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

router = APIRouter()


class ModerationDecisionPayload(BaseModel):
    comment: str | None = Field(default=None, max_length=2000)


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
    return (
        db.query(Item)
        .options(selectinload(Item.images))
        .filter(Item.status == "pending_review")
        .order_by(Item.created_at.asc())
        .all()
    )


@router.get("/items/{item_id}", response_model=ItemRead)
def read_item_for_moderation(
    item_id: UUID,
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return _get_item_for_moderation(db, item_id)


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
    db.refresh(item)
    return item


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
    db.refresh(item)
    return item


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
    db.refresh(item)
    return item