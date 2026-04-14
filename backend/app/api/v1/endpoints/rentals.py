from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.item import Item
from app.models.notification import Notification
from app.models.rental import Rental
from app.models.user import User
from app.schemas.rental import RentalCreate, RentalDecisionPayload, RentalRead

router = APIRouter()


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


def _get_owned_item_or_404(db: Session, item_id: UUID, owner_id: UUID) -> Item:
    item = db.query(Item).filter(Item.id == item_id, Item.owner_id == owner_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


def _get_rental_or_404(db: Session, rental_id: UUID) -> Rental:
    rental = db.query(Rental).filter(Rental.id == rental_id).first()
    if not rental:
        raise HTTPException(status_code=404, detail="Rental not found")
    return rental


def _has_approved_overlap(db: Session, item_id: UUID, start_date, end_date, exclude_rental_id: UUID | None = None) -> bool:
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


@router.get("/{rental_id}", response_model=RentalRead)
def read_rental(
    rental_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rental = _get_rental_or_404(db, rental_id)
    item = db.query(Item).filter(Item.id == rental.item_id).first()

    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    if rental.renter_id != current_user.id and item.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    return _to_rental_read(db, rental)


@router.post("/{rental_id}/approve", response_model=RentalRead)
def approve_rental(
    rental_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rental = _get_rental_or_404(db, rental_id)
    item = _get_owned_item_or_404(db, rental.item_id, current_user.id)

    if rental.status != "pending":
        raise HTTPException(status_code=400, detail="Only pending rental can be approved")

    if _has_approved_overlap(db, rental.item_id, rental.start_date, rental.end_date, exclude_rental_id=rental.id):
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
    item = _get_owned_item_or_404(db, rental.item_id, current_user.id)

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


@router.post("/{rental_id}/cancel", response_model=RentalRead)
def cancel_rental(
    rental_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rental = _get_rental_or_404(db, rental_id)

    if rental.renter_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only renter can cancel rental")

    if rental.status != "pending":
        raise HTTPException(status_code=400, detail="Only pending rental can be cancelled")

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
    db.commit()
    db.refresh(rental)
    return _to_rental_read(db, rental)