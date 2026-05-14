from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.modules.deliveries.models.delivery import Delivery
from app.models.item import Item
from app.models.notification import Notification
from app.modules.orders.models.order import Order, OrderItem
from app.models.user import User
from app.modules.deliveries.schemas.delivery import (
    DeliveryComplete,
    DeliveryCreate,
    DeliveryRead,
    DeliveryReturnRequest,
)

router = APIRouter()


def _now() -> datetime:
    return datetime.now(timezone.utc)


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
    if (
        delivery.renter_id != current_user.id
        and delivery.owner_id != current_user.id
        and not current_user.is_superuser
    ):
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
    elif "delivery_in_progress" in statuses:
        order.status = "delivery_in_progress"

    order.updated_at = _now()
    db.add(order)


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

    if order_item.owner_id != current_user.id and not current_user.is_superuser:
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

    if delivery.renter_id != current_user.id and not current_user.is_superuser:
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

    if delivery.renter_id != current_user.id and not current_user.is_superuser:
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