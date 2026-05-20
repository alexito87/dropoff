from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.admin import is_admin, require_admin
from app.events.notification_events import add_notification_created_event_to_outbox
from app.modules.notifications.models.notification import Notification
from app.modules.notifications.schemas.notification import NotificationCreate, NotificationRead
from app.modules.users.models.user import User

router = APIRouter()


def _get_user_or_404(db: Session, user_id: UUID) -> User:
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user


def _get_notification_or_404(db: Session, notification_id: UUID) -> Notification:
    notification = db.query(Notification).filter(Notification.id == notification_id).first()

    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    return notification


def _assert_notification_access(
    *,
    notification: Notification,
    current_user: User,
) -> None:
    if is_admin(current_user):
        return

    if notification.user_id == current_user.id:
        return

    raise HTTPException(status_code=403, detail="Access denied")


def _create_notification(
    db: Session,
    *,
    user_id: UUID,
    notification_type: str,
    payload: dict,
) -> Notification:
    notification = Notification(
        user_id=user_id,
        type=notification_type,
        payload=payload,
    )

    db.add(notification)
    db.flush()

    add_notification_created_event_to_outbox(
        db,
        notification=notification,
    )

    return notification


@router.get("/me", response_model=list[NotificationRead])
def read_my_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .all()
    )


@router.post("/{notification_id}/read", response_model=NotificationRead)
def mark_notification_as_read(
    notification_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    notification = _get_notification_or_404(db, notification_id)

    _assert_notification_access(
        notification=notification,
        current_user=current_user,
    )

    notification.is_read = True

    db.add(notification)
    db.commit()
    db.refresh(notification)

    return notification


@router.get("/admin", response_model=list[NotificationRead])
def read_all_notifications_as_admin(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    return (
        db.query(Notification)
        .order_by(Notification.created_at.desc())
        .limit(500)
        .all()
    )


@router.get("/admin/users/{user_id}", response_model=list[NotificationRead])
def read_user_notifications_as_admin(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    _get_user_or_404(db, user_id)

    return (
        db.query(Notification)
        .filter(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .limit(500)
        .all()
    )


@router.post("/admin", response_model=NotificationRead, status_code=status.HTTP_201_CREATED)
def create_notification_as_admin(
    payload: NotificationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    _get_user_or_404(db, payload.user_id)

    notification = _create_notification(
        db,
        user_id=payload.user_id,
        notification_type=payload.type,
        payload=payload.payload,
    )

    db.commit()
    db.refresh(notification)

    return notification


@router.post("/admin/{notification_id}/read", response_model=NotificationRead)
def mark_any_notification_as_read_as_admin(
    notification_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    notification = _get_notification_or_404(db, notification_id)

    notification.is_read = True

    db.add(notification)
    db.commit()
    db.refresh(notification)

    return notification


@router.delete("/admin/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_notification_as_admin(
    notification_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    notification = _get_notification_or_404(db, notification_id)

    db.delete(notification)
    db.commit()

    return None