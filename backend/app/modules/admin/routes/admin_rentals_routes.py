from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.admin import require_admin
from app.events.rental_events import (
    add_rental_cancelled_event_to_outbox,
    add_rental_completed_event_to_outbox,
    add_rental_started_event_to_outbox,
)
from app.models.audit_log_event import AuditLogEvent
from app.modules.admin.schemas.admin_rentals import (
    AdminRentalActionPayload,
    AdminRentalForceStatusPayload,
)
from app.modules.items.models.item import Item
from app.modules.rentals.models.rental import Rental
from app.modules.rentals.schemas.rental import RentalRead
from app.modules.users.models.user import User

router = APIRouter()


RENTAL_ALLOWED_STATUSES = {
    "pending",
    "approved",
    "active",
    "completed",
    "cancelled",
    "rejected",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _days_count(rental: Rental) -> int:
    return (rental.end_date - rental.start_date).days + 1


def _get_rental_or_404(db: Session, rental_id: UUID) -> Rental:
    rental = db.query(Rental).filter(Rental.id == rental_id).first()

    if not rental:
        raise HTTPException(status_code=404, detail="Rental not found")

    return rental


def _get_item_or_none(db: Session, item_id: UUID) -> Item | None:
    return db.query(Item).filter(Item.id == item_id).first()


def _get_user_or_none(db: Session, user_id: UUID) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def _serialize_rental(db: Session, rental: Rental) -> RentalRead:
    item = _get_item_or_none(db, rental.item_id)
    renter = _get_user_or_none(db, rental.renter_id)
    owner = _get_user_or_none(db, item.owner_id) if item else None

    return RentalRead(
        id=rental.id,
        item_id=rental.item_id,
        item_title=item.title if item else "",
        renter_id=rental.renter_id,
        renter_name=renter.full_name if renter else None,
        owner_id=item.owner_id if item else UUID("00000000-0000-0000-0000-000000000000"),
        owner_name=owner.full_name if owner else None,
        status=rental.status,
        start_date=rental.start_date,
        end_date=rental.end_date,
        days_count=_days_count(rental),
        daily_price_cents=rental.daily_price_cents,
        deposit_cents=rental.deposit_cents,
        total_estimate_cents=rental.total_estimate_cents,
        owner_comment=rental.owner_comment,
        created_at=rental.created_at,
        updated_at=rental.updated_at,
    )


def _write_audit(
    db: Session,
    *,
    actor_user_id: UUID,
    action: str,
    rental: Rental,
    previous_status: str,
    new_status: str,
    reason: str | None,
    extra: dict[str, Any] | None = None,
) -> None:
    meta = {
        "rental_id": str(rental.id),
        "item_id": str(rental.item_id),
        "renter_id": str(rental.renter_id),
        "previous_status": previous_status,
        "new_status": new_status,
        "reason": reason,
    }

    if extra:
        meta.update(extra)

    db.add(
        AuditLogEvent(
            actor_user_id=actor_user_id,
            action=action,
            entity_type="Rental",
            entity_id=rental.id,
            meta=meta,
        )
    )


def _rental_result(
    *,
    action: str,
    rental: Rental,
    previous_status: str,
    published_events: list[str],
    reason: str | None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = {
        "service": "admin-rentals",
        "action": action,
        "rental_id": str(rental.id),
        "item_id": str(rental.item_id),
        "renter_id": str(rental.renter_id),
        "previous_status": previous_status,
        "new_status": rental.status,
        "published_events": published_events,
        "reason": reason,
    }

    if extra:
        result.update(extra)

    return result


@router.get("", response_model=list[RentalRead])
def read_rentals_as_admin(
    status: str | None = Query(default=None),
    item_id: UUID | None = Query(default=None),
    renter_id: UUID | None = Query(default=None),
    owner_id: UUID | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    if status and status not in RENTAL_ALLOWED_STATUSES:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Unsupported rental status",
                "allowed_statuses": sorted(RENTAL_ALLOWED_STATUSES),
            },
        )

    query = db.query(Rental)

    if status:
        query = query.filter(Rental.status == status)

    if item_id:
        query = query.filter(Rental.item_id == item_id)

    if renter_id:
        query = query.filter(Rental.renter_id == renter_id)

    if owner_id:
        query = query.join(Item, Item.id == Rental.item_id).filter(Item.owner_id == owner_id)

    rentals = (
        query
        .order_by(Rental.updated_at.desc())
        .limit(limit)
        .all()
    )

    return [_serialize_rental(db, rental) for rental in rentals]


@router.get("/item/{item_id}", response_model=list[RentalRead])
def read_rentals_by_item_as_admin(
    item_id: UUID,
    limit: int = Query(default=100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    rentals = (
        db.query(Rental)
        .filter(Rental.item_id == item_id)
        .order_by(Rental.updated_at.desc())
        .limit(limit)
        .all()
    )

    return [_serialize_rental(db, rental) for rental in rentals]


@router.get("/renter/{renter_id}", response_model=list[RentalRead])
def read_rentals_by_renter_as_admin(
    renter_id: UUID,
    limit: int = Query(default=100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    rentals = (
        db.query(Rental)
        .filter(Rental.renter_id == renter_id)
        .order_by(Rental.updated_at.desc())
        .limit(limit)
        .all()
    )

    return [_serialize_rental(db, rental) for rental in rentals]


@router.get("/owner/{owner_id}", response_model=list[RentalRead])
def read_rentals_by_owner_as_admin(
    owner_id: UUID,
    limit: int = Query(default=100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    rentals = (
        db.query(Rental)
        .join(Item, Item.id == Rental.item_id)
        .filter(Item.owner_id == owner_id)
        .order_by(Rental.updated_at.desc())
        .limit(limit)
        .all()
    )

    return [_serialize_rental(db, rental) for rental in rentals]


@router.post("/{rental_id}/force-status")
def force_rental_status_as_admin(
    rental_id: UUID,
    payload: AdminRentalForceStatusPayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    target_status = payload.status.strip()

    if target_status not in RENTAL_ALLOWED_STATUSES:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Unsupported rental status",
                "allowed_statuses": sorted(RENTAL_ALLOWED_STATUSES),
            },
        )

    rental = _get_rental_or_404(db, rental_id)
    previous_status = rental.status
    published_events: list[str] = []

    rental.status = target_status
    rental.updated_at = _now()

    if target_status == "active":
        add_rental_started_event_to_outbox(db, rental=rental)
        published_events.append("rental.started")

    elif target_status == "completed":
        add_rental_completed_event_to_outbox(db, rental=rental)
        published_events.append("rental.completed")

    elif target_status == "cancelled":
        add_rental_cancelled_event_to_outbox(db, rental=rental)
        published_events.append("rental.cancelled")

    db.add(rental)

    _write_audit(
        db,
        actor_user_id=current_user.id,
        action="rental.force_status",
        rental=rental,
        previous_status=previous_status,
        new_status=rental.status,
        reason=payload.reason,
        extra={
            "published_events": published_events,
        },
    )

    db.commit()
    db.refresh(rental)

    return _rental_result(
        action="rental.force_status",
        rental=rental,
        previous_status=previous_status,
        published_events=published_events,
        reason=payload.reason,
    )


@router.post("/{rental_id}/force-cancel")
def force_cancel_rental_as_admin(
    rental_id: UUID,
    payload: AdminRentalActionPayload | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    rental = _get_rental_or_404(db, rental_id)
    previous_status = rental.status
    reason = payload.reason if payload else None

    if rental.status == "cancelled":
        return _rental_result(
            action="rental.force_cancel",
            rental=rental,
            previous_status=previous_status,
            published_events=[],
            reason=reason,
        )

    rental.status = "cancelled"
    rental.owner_comment = reason or rental.owner_comment
    rental.updated_at = _now()

    db.add(rental)

    add_rental_cancelled_event_to_outbox(db, rental=rental)

    _write_audit(
        db,
        actor_user_id=current_user.id,
        action="rental.force_cancel",
        rental=rental,
        previous_status=previous_status,
        new_status=rental.status,
        reason=reason,
        extra={
            "published_events": ["rental.cancelled"],
        },
    )

    db.commit()
    db.refresh(rental)

    return _rental_result(
        action="rental.force_cancel",
        rental=rental,
        previous_status=previous_status,
        published_events=["rental.cancelled"],
        reason=reason,
    )


@router.post("/{rental_id}/force-complete")
def force_complete_rental_as_admin(
    rental_id: UUID,
    payload: AdminRentalActionPayload | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    rental = _get_rental_or_404(db, rental_id)
    previous_status = rental.status
    reason = payload.reason if payload else None

    if rental.status == "completed":
        return _rental_result(
            action="rental.force_complete",
            rental=rental,
            previous_status=previous_status,
            published_events=[],
            reason=reason,
        )

    rental.status = "completed"
    rental.owner_comment = reason or rental.owner_comment
    rental.updated_at = _now()

    db.add(rental)

    add_rental_completed_event_to_outbox(db, rental=rental)

    _write_audit(
        db,
        actor_user_id=current_user.id,
        action="rental.force_complete",
        rental=rental,
        previous_status=previous_status,
        new_status=rental.status,
        reason=reason,
        extra={
            "published_events": ["rental.completed"],
        },
    )

    db.commit()
    db.refresh(rental)

    return _rental_result(
        action="rental.force_complete",
        rental=rental,
        previous_status=previous_status,
        published_events=["rental.completed"],
        reason=reason,
    )