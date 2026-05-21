from math import ceil
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.admin import require_admin
from app.events.notification_events import add_notification_created_event_to_outbox
from app.models.audit_log_event import AuditLogEvent
from app.modules.admin.schemas.admin_notifications import (
    AdminNotificationActionPayload,
    AdminNotificationRead,
    AdminNotificationsResponse,
    AdminNotificationUserRead,
    AdminServiceNotificationCreate,
)
from app.modules.notifications.models.notification import Notification
from app.modules.users.models.user import User

router = APIRouter()


def _get_user_or_404(db: Session, user_id: UUID) -> User:
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user


def _get_user_or_none(db: Session, user_id: UUID) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def _get_notification_or_404(db: Session, notification_id: UUID) -> Notification:
    notification = db.query(Notification).filter(Notification.id == notification_id).first()

    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    return notification


def _serialize_user(user: User | None) -> AdminNotificationUserRead | None:
    if not user:
        return None

    return AdminNotificationUserRead(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        email_verified=user.email_verified,
    )


def _serialize_notification(db: Session, notification: Notification) -> AdminNotificationRead:
    user = _get_user_or_none(db, notification.user_id)

    return AdminNotificationRead(
        id=notification.id,
        user_id=notification.user_id,
        user=_serialize_user(user),
        type=notification.type,
        payload=notification.payload or {},
        is_read=notification.is_read,
        created_at=notification.created_at,
    )


def _write_audit(
    db: Session,
    *,
    actor_user_id: UUID,
    action: str,
    entity_type: str,
    entity_id: UUID | None,
    reason: str | None,
    extra: dict[str, Any] | None = None,
) -> None:
    meta = {
        "reason": reason,
    }

    if extra:
        meta.update(extra)

    db.add(
        AuditLogEvent(
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            meta=meta,
        )
    )


@router.get("", response_model=AdminNotificationsResponse)
def read_notifications_as_admin(
    user_id: UUID | None = Query(default=None),
    type: str | None = Query(default=None),
    is_read: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    base_query = db.query(Notification)

    if user_id:
        base_query = base_query.filter(Notification.user_id == user_id)

    if type:
        base_query = base_query.filter(Notification.type == type)

    if is_read is not None:
        base_query = base_query.filter(Notification.is_read == is_read)

    total = base_query.count()
    pages = ceil(total / page_size) if total > 0 else 1
    offset = (page - 1) * page_size

    notifications = (
        base_query
        .order_by(Notification.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    return AdminNotificationsResponse(
        notifications=[_serialize_notification(db, notification) for notification in notifications],
        page=page,
        page_size=page_size,
        total=total,
        pages=pages,
    )


@router.get("/unread", response_model=AdminNotificationsResponse)
def read_unread_notifications_as_admin(
    user_id: UUID | None = Query(default=None),
    type: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    base_query = db.query(Notification).filter(Notification.is_read.is_(False))

    if user_id:
        base_query = base_query.filter(Notification.user_id == user_id)

    if type:
        base_query = base_query.filter(Notification.type == type)

    total = base_query.count()
    pages = ceil(total / page_size) if total > 0 else 1
    offset = (page - 1) * page_size

    notifications = (
        base_query
        .order_by(Notification.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    return AdminNotificationsResponse(
        notifications=[_serialize_notification(db, notification) for notification in notifications],
        page=page,
        page_size=page_size,
        total=total,
        pages=pages,
    )


@router.get("/type/{notification_type}", response_model=AdminNotificationsResponse)
def read_notifications_by_type_as_admin(
    notification_type: str,
    user_id: UUID | None = Query(default=None),
    is_read: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    base_query = db.query(Notification).filter(Notification.type == notification_type)

    if user_id:
        base_query = base_query.filter(Notification.user_id == user_id)

    if is_read is not None:
        base_query = base_query.filter(Notification.is_read == is_read)

    total = base_query.count()
    pages = ceil(total / page_size) if total > 0 else 1
    offset = (page - 1) * page_size

    notifications = (
        base_query
        .order_by(Notification.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    return AdminNotificationsResponse(
        notifications=[_serialize_notification(db, notification) for notification in notifications],
        page=page,
        page_size=page_size,
        total=total,
        pages=pages,
    )


@router.get("/users/{user_id}", response_model=AdminNotificationsResponse)
def read_user_notifications_as_admin(
    user_id: UUID,
    type: str | None = Query(default=None),
    is_read: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    _get_user_or_404(db, user_id)

    base_query = db.query(Notification).filter(Notification.user_id == user_id)

    if type:
        base_query = base_query.filter(Notification.type == type)

    if is_read is not None:
        base_query = base_query.filter(Notification.is_read == is_read)

    total = base_query.count()
    pages = ceil(total / page_size) if total > 0 else 1
    offset = (page - 1) * page_size

    notifications = (
        base_query
        .order_by(Notification.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    return AdminNotificationsResponse(
        notifications=[_serialize_notification(db, notification) for notification in notifications],
        page=page,
        page_size=page_size,
        total=total,
        pages=pages,
    )


@router.post("/service", response_model=AdminNotificationRead)
def create_service_notification_as_admin(
    payload: AdminServiceNotificationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    user = _get_user_or_404(db, payload.user_id)

    notification = Notification(
        user_id=user.id,
        type=payload.type,
        payload=payload.payload,
        is_read=False,
    )

    db.add(notification)
    db.flush()

    add_notification_created_event_to_outbox(
        db,
        notification=notification,
    )

    _write_audit(
        db,
        actor_user_id=current_user.id,
        action="notification.create_service",
        entity_type="Notification",
        entity_id=notification.id,
        reason=payload.reason,
        extra={
            "user_id": str(user.id),
            "email": user.email,
            "notification_type": notification.type,
            "payload": notification.payload,
            "published_events": ["notification.created"],
        },
    )

    db.commit()
    db.refresh(notification)

    return _serialize_notification(db, notification)


@router.post("/users/{user_id}/mark-all-read")
def mark_all_user_notifications_read_as_admin(
    user_id: UUID,
    payload: AdminNotificationActionPayload | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    user = _get_user_or_404(db, user_id)
    reason = payload.reason if payload else None

    notifications = (
        db.query(Notification)
        .filter(
            Notification.user_id == user.id,
            Notification.is_read.is_(False),
        )
        .all()
    )

    for notification in notifications:
        notification.is_read = True
        db.add(notification)

    _write_audit(
        db,
        actor_user_id=current_user.id,
        action="notification.mark_all_user_read",
        entity_type="User",
        entity_id=user.id,
        reason=reason,
        extra={
            "user_id": str(user.id),
            "email": user.email,
            "changed_notifications": len(notifications),
        },
    )

    db.commit()

    return {
        "service": "admin-notifications",
        "action": "notification.mark_all_user_read",
        "user_id": str(user.id),
        "email": user.email,
        "changed_notifications": len(notifications),
        "reason": reason,
    }


@router.delete("/users/{user_id}")
def delete_all_user_notifications_as_admin(
    user_id: UUID,
    payload: AdminNotificationActionPayload | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    user = _get_user_or_404(db, user_id)
    reason = payload.reason if payload else None

    notifications = (
        db.query(Notification)
        .filter(Notification.user_id == user.id)
        .all()
    )

    deleted_count = len(notifications)

    for notification in notifications:
        db.delete(notification)

    _write_audit(
        db,
        actor_user_id=current_user.id,
        action="notification.delete_all_user",
        entity_type="User",
        entity_id=user.id,
        reason=reason,
        extra={
            "user_id": str(user.id),
            "email": user.email,
            "deleted_notifications": deleted_count,
        },
    )

    db.commit()

    return {
        "service": "admin-notifications",
        "action": "notification.delete_all_user",
        "user_id": str(user.id),
        "email": user.email,
        "deleted_notifications": deleted_count,
        "reason": reason,
    }


@router.post("/{notification_id}/mark-read", response_model=AdminNotificationRead)
def mark_notification_read_as_admin(
    notification_id: UUID,
    payload: AdminNotificationActionPayload | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    notification = _get_notification_or_404(db, notification_id)
    reason = payload.reason if payload else None
    previous_is_read = notification.is_read

    notification.is_read = True
    db.add(notification)

    _write_audit(
        db,
        actor_user_id=current_user.id,
        action="notification.mark_read",
        entity_type="Notification",
        entity_id=notification.id,
        reason=reason,
        extra={
            "user_id": str(notification.user_id),
            "previous_is_read": previous_is_read,
            "new_is_read": notification.is_read,
        },
    )

    db.commit()
    db.refresh(notification)

    return _serialize_notification(db, notification)


@router.delete("/{notification_id}")
def delete_notification_as_admin(
    notification_id: UUID,
    payload: AdminNotificationActionPayload | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    notification = _get_notification_or_404(db, notification_id)
    reason = payload.reason if payload else None

    notification_snapshot = {
        "notification_id": str(notification.id),
        "user_id": str(notification.user_id),
        "type": notification.type,
        "payload": notification.payload,
        "is_read": notification.is_read,
        "created_at": notification.created_at.isoformat() if notification.created_at else None,
    }

    db.delete(notification)

    _write_audit(
        db,
        actor_user_id=current_user.id,
        action="notification.delete",
        entity_type="Notification",
        entity_id=notification_id,
        reason=reason,
        extra=notification_snapshot,
    )

    db.commit()

    return {
        "service": "admin-notifications",
        "action": "notification.delete",
        "notification_id": str(notification_id),
        "reason": reason,
    }