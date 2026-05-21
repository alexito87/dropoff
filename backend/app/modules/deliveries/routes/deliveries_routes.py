from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.events.delivery_events import (
    add_delivery_cancelled_event_to_outbox,
    add_delivery_completed_event_to_outbox,
    add_delivery_created_event_to_outbox,
    add_delivery_return_requested_event_to_outbox,
)
from app.models.item import Item
from app.models.notification import Notification
from app.models.user import User
from app.modules.deliveries.models.delivery import Delivery
from app.modules.deliveries.schemas.delivery import (
    DeliveryComplete,
    DeliveryCreate,
    DeliveryRead,
    DeliveryReturnRequest,
)
from app.modules.orders.models.order import Order, OrderItem

router = APIRouter()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _is_admin(user: User) -> bool:
    return bool(getattr(user, "is_superuser", False))


def _create_notification(db: Session, user_id: UUID, notification_type: str, payload: dict) -> None:
    db.add(
        Notification(
            user_id=user_id,
            type=notification_type,
            payload=payload,
        )
    )


def _get_order_item_or_404(db: Session, order_item_id: UUID) -> OrderItem:
    order_item = db.query(OrderItem).filter(OrderItem.id == order_item_id).first()

    if not order_item:
        raise HTTPException(status_code=404, detail="Order item not found")

    return order_item


def _get_order_or_404(db: Session, order_id: UUID) -> Order:
    order = db.query(Order).filter(Order.id == order_id).first()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    return order


def _get_delivery_or_404(db: Session, delivery_id: UUID) -> Delivery:
    delivery = db.query(Delivery).filter(Delivery.id == delivery_id).first()

    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")

    return delivery


def _ensure_delivery_access(delivery: Delivery, current_user: User) -> None:
    if _is_admin(current_user):
        return

    if delivery.renter_id == current_user.id:
        return

    if delivery.owner_id == current_user.id:
        return

    raise HTTPException(status_code=403, detail="Access denied")


def _sync_order_status_after_item_change(db: Session, order: Order) -> None:
    order_items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
    statuses = {item.status for item in order_items}

    if not order_items:
        return

    if statuses == {"active"}:
        order.status = "active"
    elif "return_requested" in statuses:
        order.status = "return_requested"
    elif "delivery_cancelled" in statuses:
        order.status = "delivery_cancelled"
    elif "delivery_in_progress" in statuses or "in_delivery" in statuses:
        order.status = "delivery_in_progress"

    order.updated_at = _now()
    db.add(order)


@router.get("/admin", response_model=list[DeliveryRead])
def read_all_deliveries_as_admin(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Only admin can read all deliveries")

    deliveries = (
        db.query(Delivery)
        .order_by(Delivery.updated_at.desc())
        .limit(200)
        .all()
    )

    return deliveries


@router.post("", response_model=DeliveryRead, status_code=status.HTTP_201_CREATED)
def start_delivery(
    payload: DeliveryCreate,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order_item = _get_order_item_or_404(db, payload.order_item_id)
    order = _get_order_or_404(db, order_item.order_id)

    if order.status != "paid" and order_item.status != "paid":
        raise HTTPException(
            status_code=400,
            detail="Delivery can be started only for paid order item",
        )

    if order_item.owner_id != current_user.id and not _is_admin(current_user):
        raise HTTPException(
            status_code=403,
            detail="Only item owner or admin can start delivery",
        )

    existing_delivery = (
        db.query(Delivery)
        .filter(Delivery.order_item_id == order_item.id)
        .first()
    )

    if existing_delivery:
        raise HTTPException(status_code=400, detail="Delivery already exists for this order item")

    item = db.query(Item).filter(Item.id == order_item.item_id).first()

    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    now = _now()

    delivery = Delivery(
        order_id=order.id,
        order_item_id=order_item.id,
        item_id=order_item.item_id,
        renter_id=order.user_id,
        owner_id=order_item.owner_id,
        status="in_progress",
        courier_name=payload.courier_name,
        current_location=payload.current_location,
        started_at=payload.started_at or now,
        created_at=now,
        updated_at=now,
    )

    order_item.status = "delivery_in_progress"
    order_item.updated_at = now

    if order.status == "paid":
        order.status = "delivery_in_progress"
        order.updated_at = now

    db.add(delivery)
    db.add(order_item)
    db.add(order)
    db.flush()

    add_delivery_created_event_to_outbox(
        db,
        delivery=delivery,
        actor_user_id=current_user.id,
    )

    _create_notification(
        db,
        order.user_id,
        "delivery_started",
        {
            "order_id": str(order.id),
            "order_item_id": str(order_item.id),
            "item_id": str(order_item.item_id),
            "item_title": item.title,
            "status": "delivery_in_progress",
        },
    )

    _create_notification(
        db,
        order_item.owner_id,
        "delivery_acquired",
        {
            "order_id": str(order.id),
            "order_item_id": str(order_item.id),
            "item_id": str(order_item.item_id),
            "item_title": item.title,
            "status": "delivery_in_progress",
        },
    )

    db.commit()
    db.refresh(delivery)

    response.headers["Location"] = f"/api/v1/deliveries/{delivery.id}"

    return delivery


@router.get("/{delivery_id}", response_model=DeliveryRead)
def delivery_details(
    delivery_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    delivery = _get_delivery_or_404(db, delivery_id)

    _ensure_delivery_access(delivery, current_user)

    return delivery


@router.post("/{delivery_id}/complete", response_model=DeliveryRead)
def complete_delivery(
    delivery_id: UUID,
    payload: DeliveryComplete,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    delivery = _get_delivery_or_404(db, delivery_id)

    _ensure_delivery_access(delivery, current_user)

    if delivery.renter_id != current_user.id and not _is_admin(current_user):
        raise HTTPException(
            status_code=403,
            detail="Only renter or admin can confirm delivery completion",
        )

    if delivery.status != "in_progress":
        raise HTTPException(status_code=400, detail="Only in_progress delivery can be completed")

    order_item = _get_order_item_or_404(db, delivery.order_item_id)
    order = _get_order_or_404(db, delivery.order_id)
    item = db.query(Item).filter(Item.id == delivery.item_id).first()

    now = _now()

    delivery.status = "delivered"
    delivery.final_location = payload.final_location
    delivery.finished_at = payload.finished_at or now
    delivery.updated_at = now

    order_item.status = "active"
    order_item.updated_at = now

    _sync_order_status_after_item_change(db, order)

    db.add(delivery)
    db.add(order_item)
    db.flush()

    add_delivery_completed_event_to_outbox(
        db,
        delivery=delivery,
        actor_user_id=current_user.id,
    )

    _create_notification(
        db,
        delivery.renter_id,
        "delivery_completed",
        {
            "order_id": str(order.id),
            "order_item_id": str(order_item.id),
            "item_id": str(delivery.item_id),
            "item_title": item.title if item else "",
            "status": "active",
        },
    )

    _create_notification(
        db,
        delivery.owner_id,
        "rental_started",
        {
            "order_id": str(order.id),
            "order_item_id": str(order_item.id),
            "item_id": str(delivery.item_id),
            "item_title": item.title if item else "",
            "status": "active",
        },
    )

    db.commit()
    db.refresh(delivery)

    return delivery


@router.post("/{delivery_id}/return-request", response_model=DeliveryRead)
def request_delivery_return(
    delivery_id: UUID,
    payload: DeliveryReturnRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    delivery = _get_delivery_or_404(db, delivery_id)

    _ensure_delivery_access(delivery, current_user)

    if delivery.renter_id != current_user.id and not _is_admin(current_user):
        raise HTTPException(
            status_code=403,
            detail="Only renter or admin can request return",
        )

    if delivery.status != "in_progress":
        raise HTTPException(status_code=400, detail="Return can be requested only for in_progress delivery")

    order_item = _get_order_item_or_404(db, delivery.order_item_id)
    order = _get_order_or_404(db, delivery.order_id)
    item = db.query(Item).filter(Item.id == delivery.item_id).first()

    now = _now()

    delivery.status = "return_requested"
    delivery.return_reason = payload.reason
    delivery.updated_at = now

    order_item.status = "return_requested"
    order_item.updated_at = now

    order.status = "return_requested"
    order.updated_at = now

    db.add(delivery)
    db.add(order_item)
    db.add(order)
    db.flush()

    add_delivery_return_requested_event_to_outbox(
        db,
        delivery=delivery,
        actor_user_id=current_user.id,
    )

    _create_notification(
        db,
        delivery.renter_id,
        "delivery_return_requested",
        {
            "order_id": str(order.id),
            "order_item_id": str(order_item.id),
            "item_id": str(delivery.item_id),
            "item_title": item.title if item else "",
            "status": "return_requested",
            "reason": payload.reason,
        },
    )

    _create_notification(
        db,
        delivery.owner_id,
        "delivery_return_requested",
        {
            "order_id": str(order.id),
            "order_item_id": str(order_item.id),
            "item_id": str(delivery.item_id),
            "item_title": item.title if item else "",
            "status": "return_requested",
            "reason": payload.reason,
        },
    )

    db.commit()
    db.refresh(delivery)

    return delivery


@router.post("/{delivery_id}/cancel", response_model=DeliveryRead)
def cancel_delivery(
    delivery_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    delivery = _get_delivery_or_404(db, delivery_id)

    _ensure_delivery_access(delivery, current_user)

    if delivery.owner_id != current_user.id and not _is_admin(current_user):
        raise HTTPException(
            status_code=403,
            detail="Only owner or admin can cancel delivery",
        )

    if delivery.status not in {"in_progress", "return_requested"}:
        raise HTTPException(
            status_code=400,
            detail="Only in_progress or return_requested delivery can be cancelled",
        )

    order_item = _get_order_item_or_404(db, delivery.order_item_id)
    order = _get_order_or_404(db, delivery.order_id)
    item = db.query(Item).filter(Item.id == delivery.item_id).first()

    now = _now()

    delivery.status = "cancelled"
    delivery.finished_at = delivery.finished_at or now
    delivery.updated_at = now

    order_item.status = "delivery_cancelled"
    order_item.updated_at = now

    _sync_order_status_after_item_change(db, order)

    db.add(delivery)
    db.add(order_item)
    db.add(order)
    db.flush()

    add_delivery_cancelled_event_to_outbox(
        db,
        delivery=delivery,
        actor_user_id=current_user.id,
    )

    _create_notification(
        db,
        delivery.renter_id,
        "delivery_cancelled",
        {
            "order_id": str(order.id),
            "order_item_id": str(order_item.id),
            "item_id": str(delivery.item_id),
            "item_title": item.title if item else "",
            "status": "delivery_cancelled",
        },
    )

    _create_notification(
        db,
        delivery.owner_id,
        "delivery_cancelled",
        {
            "order_id": str(order.id),
            "order_item_id": str(order_item.id),
            "item_id": str(delivery.item_id),
            "item_title": item.title if item else "",
            "status": "delivery_cancelled",
        },
    )

    db.commit()
    db.refresh(delivery)

    return delivery