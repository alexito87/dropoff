from math import ceil
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.admin import require_admin
from app.models.audit_log_event import AuditLogEvent
from app.modules.admin.schemas.admin_users import (
    AdminUserProfileResetPayload,
    AdminUserRead,
    AdminUserRelatedSummary,
    AdminUsersResponse,
    AdminUserStatusPayload,
    AdminUserSuperuserPayload,
)
from app.modules.deliveries.models.delivery import Delivery
from app.modules.items.models.item import Item
from app.modules.notifications.models.notification import Notification
from app.modules.orders.models.cart import Cart, CartItem
from app.modules.orders.models.order import Order, OrderItem
from app.modules.payments.models.payment import Payment
from app.modules.rentals.models.rental import Rental
from app.modules.users.models.user import User

router = APIRouter()


def _get_user_or_404(db: Session, user_id: UUID) -> User:
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user


def _serialize_user(user: User) -> AdminUserRead:
    return AdminUserRead(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        phone=user.phone,
        city=user.city,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        email_verified=user.email_verified,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


def _write_audit(
    db: Session,
    *,
    actor_user_id: UUID,
    action: str,
    user: User,
    reason: str | None,
    extra: dict[str, Any] | None = None,
) -> None:
    meta = {
        "user_id": str(user.id),
        "email": user.email,
        "reason": reason,
    }

    if extra:
        meta.update(extra)

    db.add(
        AuditLogEvent(
            actor_user_id=actor_user_id,
            action=action,
            entity_type="User",
            entity_id=user.id,
            meta=meta,
        )
    )


def _count(db: Session, model, *filters) -> int:
    query = db.query(func.count(model.id))

    for condition in filters:
        query = query.filter(condition)

    return int(query.scalar() or 0)


def _count_by_field(db: Session, model, field_name: str, *filters) -> dict[str, int]:
    field = getattr(model, field_name)

    query = db.query(field, func.count(model.id))

    for condition in filters:
        query = query.filter(condition)

    rows = (
        query
        .group_by(field)
        .order_by(field.asc())
        .all()
    )

    return {
        str(value): int(count)
        for value, count in rows
    }


@router.get("", response_model=AdminUsersResponse)
def search_users_as_admin(
    search: str | None = Query(default=None),
    email: str | None = Query(default=None),
    full_name: str | None = Query(default=None),
    city: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    is_superuser: bool | None = Query(default=None),
    email_verified: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    base_query = db.query(User)

    if search:
        value = f"%{search.strip()}%"
        base_query = base_query.filter(
            or_(
                User.email.ilike(value),
                User.full_name.ilike(value),
                User.city.ilike(value),
                User.phone.ilike(value),
            )
        )

    if email:
        base_query = base_query.filter(User.email.ilike(f"%{email.strip()}%"))

    if full_name:
        base_query = base_query.filter(User.full_name.ilike(f"%{full_name.strip()}%"))

    if city:
        base_query = base_query.filter(User.city.ilike(f"%{city.strip()}%"))

    if is_active is not None:
        base_query = base_query.filter(User.is_active == is_active)

    if is_superuser is not None:
        base_query = base_query.filter(User.is_superuser == is_superuser)

    if email_verified is not None:
        base_query = base_query.filter(User.email_verified == email_verified)

    total = base_query.count()
    pages = ceil(total / page_size) if total > 0 else 1
    offset = (page - 1) * page_size

    users = (
        base_query
        .order_by(User.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    return AdminUsersResponse(
        users=[_serialize_user(user) for user in users],
        page=page,
        page_size=page_size,
        total=total,
        pages=pages,
    )


@router.get("/{user_id}", response_model=AdminUserRead)
def read_user_account_as_admin(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    user = _get_user_or_404(db, user_id)

    return _serialize_user(user)


@router.get("/{user_id}/related-summary", response_model=AdminUserRelatedSummary)
def read_user_related_summary_as_admin(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    user = _get_user_or_404(db, user_id)

    item_ids_by_owner_query = db.query(Item.id).filter(Item.owner_id == user.id)

    cart_ids_by_user_query = db.query(Cart.id).filter(Cart.user_id == user.id)

    return AdminUserRelatedSummary(
        user_id=user.id,
        email=user.email,

        items_total=_count(db, Item, Item.owner_id == user.id),
        items_by_status=_count_by_field(db, Item, "status", Item.owner_id == user.id),

        rentals_as_renter_total=_count(db, Rental, Rental.renter_id == user.id),
        rentals_as_renter_by_status=_count_by_field(db, Rental, "status", Rental.renter_id == user.id),

        rentals_as_owner_total=(
            db.query(func.count(Rental.id))
            .join(Item, Item.id == Rental.item_id)
            .filter(Item.owner_id == user.id)
            .scalar()
            or 0
        ),
        rentals_as_owner_by_status={
            str(status): int(count)
            for status, count in (
                db.query(Rental.status, func.count(Rental.id))
                .join(Item, Item.id == Rental.item_id)
                .filter(Item.owner_id == user.id)
                .group_by(Rental.status)
                .order_by(Rental.status.asc())
                .all()
            )
        },

        carts_total=_count(db, Cart, Cart.user_id == user.id),
        carts_by_status=_count_by_field(db, Cart, "status", Cart.user_id == user.id),
        cart_items_total=int(
            db.query(func.count(CartItem.id))
            .filter(CartItem.cart_id.in_(cart_ids_by_user_query))
            .scalar()
            or 0
        ),

        orders_total=_count(db, Order, Order.user_id == user.id),
        orders_by_status=_count_by_field(db, Order, "status", Order.user_id == user.id),
        order_items_as_owner_total=_count(db, OrderItem, OrderItem.owner_id == user.id),
        order_items_as_owner_by_status=_count_by_field(db, OrderItem, "status", OrderItem.owner_id == user.id),

        payments_total=_count(db, Payment, Payment.payer_user_id == user.id),
        payments_by_status=_count_by_field(db, Payment, "status", Payment.payer_user_id == user.id),

        deliveries_as_renter_total=_count(db, Delivery, Delivery.renter_id == user.id),
        deliveries_as_renter_by_status=_count_by_field(db, Delivery, "status", Delivery.renter_id == user.id),

        deliveries_as_owner_total=_count(db, Delivery, Delivery.owner_id == user.id),
        deliveries_as_owner_by_status=_count_by_field(db, Delivery, "status", Delivery.owner_id == user.id),

        notifications_total=_count(db, Notification, Notification.user_id == user.id),
        unread_notifications_total=_count(
            db,
            Notification,
            Notification.user_id == user.id,
            Notification.is_read.is_(False),
        ),
        notifications_by_type=_count_by_field(db, Notification, "type", Notification.user_id == user.id),
    )


@router.post("/{user_id}/reset-profile", response_model=AdminUserRead)
def reset_user_profile_fields_as_admin(
    user_id: UUID,
    payload: AdminUserProfileResetPayload | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    user = _get_user_or_404(db, user_id)
    payload = payload or AdminUserProfileResetPayload()

    previous_values = {
        "full_name": user.full_name,
        "phone": user.phone,
        "city": user.city,
    }

    changed_fields: list[str] = []

    if payload.reset_full_name:
        user.full_name = None
        changed_fields.append("full_name")

    if payload.reset_phone:
        user.phone = None
        changed_fields.append("phone")

    if payload.reset_city:
        user.city = None
        changed_fields.append("city")

    db.add(user)

    _write_audit(
        db,
        actor_user_id=current_user.id,
        action="user.reset_profile",
        user=user,
        reason=payload.reason,
        extra={
            "changed_fields": changed_fields,
            "previous_values": previous_values,
            "new_values": {
                "full_name": user.full_name,
                "phone": user.phone,
                "city": user.city,
            },
        },
    )

    db.commit()
    db.refresh(user)

    return _serialize_user(user)


@router.post("/{user_id}/grant-superuser", response_model=AdminUserRead)
def grant_superuser_as_admin(
    user_id: UUID,
    payload: AdminUserSuperuserPayload | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    user = _get_user_or_404(db, user_id)
    reason = payload.reason if payload else None
    previous_is_superuser = bool(user.is_superuser)

    user.is_superuser = True

    db.add(user)

    _write_audit(
        db,
        actor_user_id=current_user.id,
        action="user.grant_superuser",
        user=user,
        reason=reason,
        extra={
            "previous_is_superuser": previous_is_superuser,
            "new_is_superuser": user.is_superuser,
        },
    )

    db.commit()
    db.refresh(user)

    return _serialize_user(user)


@router.post("/{user_id}/revoke-superuser", response_model=AdminUserRead)
def revoke_superuser_as_admin(
    user_id: UUID,
    payload: AdminUserSuperuserPayload | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    user = _get_user_or_404(db, user_id)
    reason = payload.reason if payload else None

    if user.id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="Admin cannot revoke own superuser permissions",
        )

    previous_is_superuser = bool(user.is_superuser)

    user.is_superuser = False

    db.add(user)

    _write_audit(
        db,
        actor_user_id=current_user.id,
        action="user.revoke_superuser",
        user=user,
        reason=reason,
        extra={
            "previous_is_superuser": previous_is_superuser,
            "new_is_superuser": user.is_superuser,
        },
    )

    db.commit()
    db.refresh(user)

    return _serialize_user(user)


@router.post("/{user_id}/activate", response_model=AdminUserRead)
def activate_user_account_as_admin(
    user_id: UUID,
    payload: AdminUserStatusPayload | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    user = _get_user_or_404(db, user_id)
    reason = payload.reason if payload else None
    previous_is_active = bool(user.is_active)

    user.is_active = True

    db.add(user)

    _write_audit(
        db,
        actor_user_id=current_user.id,
        action="user.activate",
        user=user,
        reason=reason,
        extra={
            "previous_is_active": previous_is_active,
            "new_is_active": user.is_active,
        },
    )

    db.commit()
    db.refresh(user)

    return _serialize_user(user)


@router.post("/{user_id}/deactivate", response_model=AdminUserRead)
def deactivate_user_account_as_admin(
    user_id: UUID,
    payload: AdminUserStatusPayload | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    user = _get_user_or_404(db, user_id)
    reason = payload.reason if payload else None

    if user.id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="Admin cannot deactivate own account",
        )

    previous_is_active = bool(user.is_active)

    user.is_active = False

    db.add(user)

    _write_audit(
        db,
        actor_user_id=current_user.id,
        action="user.deactivate",
        user=user,
        reason=reason,
        extra={
            "previous_is_active": previous_is_active,
            "new_is_active": user.is_active,
        },
    )

    db.commit()
    db.refresh(user)

    return _serialize_user(user)