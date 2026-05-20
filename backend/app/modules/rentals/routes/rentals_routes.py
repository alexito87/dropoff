from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.events.rental_events import (
    add_rental_cancelled_event_to_outbox,
    add_rental_completed_event_to_outbox,
    add_rental_created_event_to_outbox,
    add_rental_started_event_to_outbox,
)
from app.modules.items.models.item import Item
from app.modules.notifications.models.notification import Notification
from app.modules.rentals.models.rental import Rental
from app.modules.rentals.schemas.rental import (
    RentalCreate,
    RentalDecisionPayload,
    RentalRead,
)
from app.modules.users.models.user import User

router = APIRouter()


def _is_admin(user: User) -> bool:
    return bool(getattr(user, "is_superuser", False))


def _days_count(start_date, end_date) -> int:
    return (end_date - start_date).days + 1


def _to_rental_read(db: Session, rental: Rental) -> RentalRead:
    item = db.query(Item).filter(Item.id == rental.item_id).first()
    renter = db.query(User).filter(User.id == rental.renter_id).first()
    owner = db.query(User).filter(User.id == item.owner_id).first() if item else None

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
        days_count=_days_count(rental.start_date, rental.end_date),
        daily_price_cents=rental.daily_price_cents,
        deposit_cents=rental.deposit_cents,
        total_estimate_cents=rental.total_estimate_cents,
        owner_comment=rental.owner_comment,
        created_at=rental.created_at,
        updated_at=rental.updated_at,
    )


def _create_notification(db: Session, user_id, notification_type: str, payload: dict):
    db.add(
        Notification(
            user_id=user_id,
            type=notification_type,
            payload=payload,
        )
    )


def _get_owned_item_or_404(
    db: Session,
    item_id: UUID,
    owner_id: UUID,
    *,
    current_user: User,
) -> Item:
    item = db.query(Item).filter(Item.id == item_id).first()

    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    if not _is_admin(current_user) and item.owner_id != owner_id:
        raise HTTPException(status_code=403, detail="Access denied")

    return item


def _get_rental_or_404(db: Session, rental_id: UUID) -> Rental:
    rental = db.query(Rental).filter(Rental.id == rental_id).first()

    if not rental:
        raise HTTPException(status_code=404, detail="Rental not found")

    return rental


def _get_item_or_404(db: Session, item_id: UUID) -> Item:
    item = db.query(Item).filter(Item.id == item_id).first()

    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    return item


def _assert_can_read_rental(
    *,
    rental: Rental,
    item: Item,
    current_user: User,
) -> None:
    if _is_admin(current_user):
        return

    if rental.renter_id == current_user.id:
        return

    if item.owner_id == current_user.id:
        return

    raise HTTPException(status_code=403, detail="Access denied")


def _assert_can_manage_as_owner(
    *,
    item: Item,
    current_user: User,
) -> None:
    if _is_admin(current_user):
        return

    if item.owner_id == current_user.id:
        return

    raise HTTPException(status_code=403, detail="Only item owner can perform this action")


def _assert_can_manage_as_renter(
    *,
    rental: Rental,
    current_user: User,
) -> None:
    if _is_admin(current_user):
        return

    if rental.renter_id == current_user.id:
        return

    raise HTTPException(status_code=403, detail="Only renter can perform this action")


def _assert_can_complete_rental(
    *,
    rental: Rental,
    item: Item,
    current_user: User,
) -> None:
    if _is_admin(current_user):
        return

    if item.owner_id == current_user.id:
        return

    if rental.renter_id == current_user.id:
        return

    raise HTTPException(status_code=403, detail="Only renter or owner can complete rental")


def _has_approved_overlap(
    db: Session,
    item_id: UUID,
    start_date,
    end_date,
    exclude_rental_id: UUID | None = None,
) -> bool:
    query = db.query(Rental).filter(
        Rental.item_id == item_id,
        Rental.status == "approved",
        and_(
            Rental.start_date <= end_date,
            Rental.end_date >= start_date,
        ),
    )

    if exclude_rental_id:
        query = query.filter(Rental.id != exclude_rental_id)

    return db.query(query.exists()).scalar()


@router.post("", response_model=RentalRead, status_code=status.HTTP_201_CREATED)
def create_rental(
    payload: RentalCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = db.query(Item).filter(Item.id == payload.item_id, Item.status == "published").first()

    if not item:
        raise HTTPException(status_code=404, detail="Published item not found")

    if item.owner_id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot rent your own item")

    if payload.end_date < payload.start_date:
        raise HTTPException(status_code=400, detail="End date cannot be earlier than start date")

    days_count = _days_count(payload.start_date, payload.end_date)
    total_estimate_cents = item.daily_price_cents * days_count

    rental = Rental(
        item_id=item.id,
        renter_id=current_user.id,
        status="pending",
        start_date=payload.start_date,
        end_date=payload.end_date,
        daily_price_cents=item.daily_price_cents,
        deposit_cents=item.deposit_cents,
        total_estimate_cents=total_estimate_cents,
    )

    db.add(rental)
    db.flush()

    _create_notification(
        db,
        item.owner_id,
        "rental_created",
        {
            "rental_id": str(rental.id),
            "item_id": str(item.id),
            "item_title": item.title,
            "status": "pending",
        },
    )

    add_rental_created_event_to_outbox(
        db,
        rental=rental,
    )

    db.commit()
    db.refresh(rental)

    return _to_rental_read(db, rental)


@router.get("/me", response_model=list[RentalRead])
def read_my_rentals(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rentals = (
        db.query(Rental)
        .filter(Rental.renter_id == current_user.id)
        .order_by(Rental.created_at.desc())
        .all()
    )

    return [_to_rental_read(db, rental) for rental in rentals]


@router.get("/owner", response_model=list[RentalRead])
def read_owner_rentals(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rentals = (
        db.query(Rental)
        .join(Item, Item.id == Rental.item_id)
        .filter(Item.owner_id == current_user.id)
        .order_by(Rental.created_at.desc())
        .all()
    )

    return [_to_rental_read(db, rental) for rental in rentals]


@router.get("/admin", response_model=list[RentalRead])
def read_all_rentals_as_admin(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Only admin can read all rentals")

    rentals = (
        db.query(Rental)
        .order_by(Rental.updated_at.desc())
        .limit(100)
        .all()
    )

    return [_to_rental_read(db, rental) for rental in rentals]


@router.get("/{rental_id}", response_model=RentalRead)
def read_rental(
    rental_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rental = _get_rental_or_404(db, rental_id)
    item = _get_item_or_404(db, rental.item_id)

    _assert_can_read_rental(
        rental=rental,
        item=item,
        current_user=current_user,
    )

    return _to_rental_read(db, rental)


@router.post("/{rental_id}/approve", response_model=RentalRead)
def approve_rental(
    rental_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rental = _get_rental_or_404(db, rental_id)

    item = _get_owned_item_or_404(
        db,
        rental.item_id,
        current_user.id,
        current_user=current_user,
    )

    _assert_can_manage_as_owner(
        item=item,
        current_user=current_user,
    )

    if rental.status != "pending":
        raise HTTPException(status_code=400, detail="Only pending rental can be approved")

    if _has_approved_overlap(
        db,
        rental.item_id,
        rental.start_date,
        rental.end_date,
        exclude_rental_id=rental.id,
    ):
        raise HTTPException(
            status_code=400,
            detail="Cannot approve rental because dates overlap with another approved rental",
        )

    rental.status = "approved"
    rental.updated_at = datetime.now(timezone.utc)

    _create_notification(
        db,
        rental.renter_id,
        "rental_approved",
        {
            "rental_id": str(rental.id),
            "item_id": str(item.id),
            "item_title": item.title,
            "status": rental.status,
        },
    )

    db.add(rental)
    db.commit()
    db.refresh(rental)

    return _to_rental_read(db, rental)


@router.post("/{rental_id}/reject", response_model=RentalRead)
def reject_rental(
    rental_id: UUID,
    payload: RentalDecisionPayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rental = _get_rental_or_404(db, rental_id)

    item = _get_owned_item_or_404(
        db,
        rental.item_id,
        current_user.id,
        current_user=current_user,
    )

    _assert_can_manage_as_owner(
        item=item,
        current_user=current_user,
    )

    if rental.status != "pending":
        raise HTTPException(status_code=400, detail="Only pending rental can be rejected")

    rental.status = "rejected"
    rental.owner_comment = payload.owner_comment
    rental.updated_at = datetime.now(timezone.utc)

    _create_notification(
        db,
        rental.renter_id,
        "rental_rejected",
        {
            "rental_id": str(rental.id),
            "item_id": str(item.id),
            "item_title": item.title,
            "status": rental.status,
            "owner_comment": payload.owner_comment,
        },
    )

    db.add(rental)
    db.commit()
    db.refresh(rental)

    return _to_rental_read(db, rental)


@router.post("/{rental_id}/start", response_model=RentalRead)
def start_rental(
    rental_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rental = _get_rental_or_404(db, rental_id)

    item = _get_owned_item_or_404(
        db,
        rental.item_id,
        current_user.id,
        current_user=current_user,
    )

    _assert_can_manage_as_owner(
        item=item,
        current_user=current_user,
    )

    if rental.status != "approved":
        raise HTTPException(status_code=400, detail="Only approved rental can be started")

    rental.status = "active"
    rental.updated_at = datetime.now(timezone.utc)

    _create_notification(
        db,
        rental.renter_id,
        "rental_started",
        {
            "rental_id": str(rental.id),
            "item_id": str(item.id),
            "item_title": item.title,
            "status": rental.status,
        },
    )

    db.add(rental)

    add_rental_started_event_to_outbox(
        db,
        rental=rental,
    )

    db.commit()
    db.refresh(rental)

    return _to_rental_read(db, rental)


@router.post("/{rental_id}/complete", response_model=RentalRead)
def complete_rental(
    rental_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rental = _get_rental_or_404(db, rental_id)
    item = _get_item_or_404(db, rental.item_id)

    _assert_can_complete_rental(
        rental=rental,
        item=item,
        current_user=current_user,
    )

    if rental.status != "active":
        raise HTTPException(status_code=400, detail="Only active rental can be completed")

    rental.status = "completed"
    rental.updated_at = datetime.now(timezone.utc)

    _create_notification(
        db,
        item.owner_id,
        "rental_completed",
        {
            "rental_id": str(rental.id),
            "item_id": str(item.id),
            "item_title": item.title,
            "status": rental.status,
            "completed_by_user_id": str(current_user.id),
        },
    )

    if rental.renter_id != item.owner_id:
        _create_notification(
            db,
            rental.renter_id,
            "rental_completed",
            {
                "rental_id": str(rental.id),
                "item_id": str(item.id),
                "item_title": item.title,
                "status": rental.status,
                "completed_by_user_id": str(current_user.id),
            },
        )

    db.add(rental)

    add_rental_completed_event_to_outbox(
        db,
        rental=rental,
    )

    db.commit()
    db.refresh(rental)

    return _to_rental_read(db, rental)


@router.post("/{rental_id}/cancel", response_model=RentalRead)
def cancel_rental(
    rental_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rental = _get_rental_or_404(db, rental_id)

    _assert_can_manage_as_renter(
        rental=rental,
        current_user=current_user,
    )

    if rental.status not in {"pending", "approved"}:
        raise HTTPException(status_code=400, detail="Only pending or approved rental can be cancelled")

    item = db.query(Item).filter(Item.id == rental.item_id).first()

    rental.status = "cancelled"
    rental.updated_at = datetime.now(timezone.utc)

    if item:
        _create_notification(
            db,
            item.owner_id,
            "rental_cancelled",
            {
                "rental_id": str(rental.id),
                "item_id": str(item.id),
                "item_title": item.title,
                "status": rental.status,
            },
        )

    db.add(rental)

    add_rental_cancelled_event_to_outbox(
        db,
        rental=rental,
    )

    db.commit()
    db.refresh(rental)

    return _to_rental_read(db, rental)