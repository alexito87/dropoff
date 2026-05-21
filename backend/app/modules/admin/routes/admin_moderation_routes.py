from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, get_db
from app.core.admin import require_admin
from app.events.moderation_events import (
    add_item_approved_event_to_outbox,
    add_item_needs_changes_event_to_outbox,
    add_item_rejected_event_to_outbox,
)
from app.modules.admin.schemas.admin_moderation import (
    AdminEmailVerificationPayload,
    AdminModerationDecisionPayload,
)
from app.modules.items.models.item import Item
from app.modules.items.models.item_image import ItemImage
from app.modules.items.schemas.item import ItemRead
from app.modules.items.schemas.item_image import ItemImageRead
from app.modules.users.models.user import User

router = APIRouter()


ITEM_STATUSES = {
    "draft",
    "pending_review",
    "published",
    "rejected",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_user_or_404(db: Session, user_id: UUID) -> User:
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user


def _get_item_or_404(db: Session, item_id: UUID) -> Item:
    item = (
        db.query(Item)
        .options(selectinload(Item.images))
        .filter(Item.id == item_id)
        .first()
    )

    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    return item


def _serialize_item_image(image: ItemImage) -> ItemImageRead:
    return ItemImageRead(
        id=image.id,
        item_id=image.item_id,
        url=image.url,
        versioned_url=image.url,
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


def _apply_moderation_state(
    *,
    item: Item,
    moderator_user_id: UUID,
    status: str,
    comment: str | None,
) -> str:
    previous_status = item.status

    item.status = status
    item.moderated_by = moderator_user_id
    item.moderated_at = _now()
    item.moderation_comment = comment
    item.updated_at = _now()

    return previous_status


@router.get("/catalog/items", response_model=list[ItemRead])
def read_admin_catalog_items(
    status: str | None = Query(default=None),
    owner_id: UUID | None = Query(default=None),
    category_id: UUID | None = Query(default=None),
    city: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
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

    query = (
        db.query(Item)
        .options(selectinload(Item.images))
    )

    if status:
        query = query.filter(Item.status == status)

    if owner_id:
        query = query.filter(Item.owner_id == owner_id)

    if category_id:
        query = query.filter(Item.category_id == category_id)

    if city:
        query = query.filter(Item.city.ilike(f"%{city.strip()}%"))

    items = (
        query
        .order_by(Item.updated_at.desc())
        .limit(limit)
        .all()
    )

    return [_serialize_item(item) for item in items]


@router.get("/moderation/items", response_model=list[ItemRead])
def read_items_for_moderation_as_admin(
    status: str = Query(default="pending_review"),
    limit: int = Query(default=100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    if status not in ITEM_STATUSES:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Unsupported item status",
                "allowed_statuses": sorted(ITEM_STATUSES),
            },
        )

    items = (
        db.query(Item)
        .options(selectinload(Item.images))
        .filter(Item.status == status)
        .order_by(Item.updated_at.desc())
        .limit(limit)
        .all()
    )

    return [_serialize_item(item) for item in items]


@router.post("/moderation/items/{item_id}/approve", response_model=ItemRead)
def approve_item_as_admin(
    item_id: UUID,
    payload: AdminModerationDecisionPayload | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    item = _get_item_or_404(db, item_id)

    previous_status = _apply_moderation_state(
        item=item,
        moderator_user_id=current_user.id,
        status="published",
        comment=payload.comment if payload else None,
    )

    db.add(item)
    db.flush()

    add_item_approved_event_to_outbox(
        db,
        item=item,
        actor_user_id=current_user.id,
        previous_status=previous_status,
    )

    db.commit()
    db.refresh(item)

    return _serialize_item(item)


@router.post("/moderation/items/{item_id}/reject", response_model=ItemRead)
def reject_item_as_admin(
    item_id: UUID,
    payload: AdminModerationDecisionPayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    item = _get_item_or_404(db, item_id)

    previous_status = _apply_moderation_state(
        item=item,
        moderator_user_id=current_user.id,
        status="rejected",
        comment=payload.comment,
    )

    db.add(item)
    db.flush()

    add_item_rejected_event_to_outbox(
        db,
        item=item,
        actor_user_id=current_user.id,
        previous_status=previous_status,
    )

    db.commit()
    db.refresh(item)

    return _serialize_item(item)


@router.post("/moderation/items/{item_id}/needs-changes", response_model=ItemRead)
def request_item_changes_as_admin(
    item_id: UUID,
    payload: AdminModerationDecisionPayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    item = _get_item_or_404(db, item_id)

    previous_status = _apply_moderation_state(
        item=item,
        moderator_user_id=current_user.id,
        status="rejected",
        comment=payload.comment,
    )

    db.add(item)
    db.flush()

    add_item_needs_changes_event_to_outbox(
        db,
        item=item,
        actor_user_id=current_user.id,
        previous_status=previous_status,
    )

    db.commit()
    db.refresh(item)

    return _serialize_item(item)


@router.post("/users/{user_id}/verify-email")
def verify_user_email_as_admin(
    user_id: UUID,
    payload: AdminEmailVerificationPayload | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    user = _get_user_or_404(db, user_id)

    previous_value = bool(user.email_verified)
    user.email_verified = True
    user.updated_at = _now()

    db.add(user)
    db.commit()
    db.refresh(user)

    return {
        "service": "admin-moderation",
        "action": "user.verify_email",
        "user_id": str(user.id),
        "email": user.email,
        "previous_email_verified": previous_value,
        "email_verified": user.email_verified,
        "reason": payload.reason if payload else None,
    }


@router.post("/users/{user_id}/unverify-email")
def unverify_user_email_as_admin(
    user_id: UUID,
    payload: AdminEmailVerificationPayload | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    user = _get_user_or_404(db, user_id)

    previous_value = bool(user.email_verified)
    user.email_verified = False
    user.updated_at = _now()

    db.add(user)
    db.commit()
    db.refresh(user)

    return {
        "service": "admin-moderation",
        "action": "user.unverify_email",
        "user_id": str(user.id),
        "email": user.email,
        "previous_email_verified": previous_value,
        "email_verified": user.email_verified,
        "reason": payload.reason if payload else None,
    }