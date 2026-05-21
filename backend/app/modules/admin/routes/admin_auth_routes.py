from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.admin import require_admin
from app.events.user_events import add_user_email_verified_event_to_outbox
from app.models.audit_log_event import AuditLogEvent
from app.modules.admin.schemas.admin_auth import (
    AdminAuthActionPayload,
    AdminResendVerificationPayload,
)
from app.modules.auth.models.email_verification_token import EmailVerificationToken
from app.modules.users.models.user import User
from app.services.email_service import send_verification_email

router = APIRouter()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_user_or_404(db: Session, user_id: UUID) -> User:
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user


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


def _token_to_dict(token: EmailVerificationToken) -> dict[str, Any]:
    return {
        "id": str(token.id),
        "user_id": str(token.user_id),
        "token": token.token,
        "expires_at": token.expires_at.isoformat() if token.expires_at else None,
        "used_at": token.used_at.isoformat() if token.used_at else None,
        "created_at": token.created_at.isoformat() if token.created_at else None,
        "is_used": token.used_at is not None,
        "is_expired": token.expires_at < _now() if token.expires_at else False,
    }


def _expire_active_tokens(db: Session, *, user_id: UUID) -> int:
    tokens = (
        db.query(EmailVerificationToken)
        .filter(
            EmailVerificationToken.user_id == user_id,
            EmailVerificationToken.used_at.is_(None),
        )
        .all()
    )

    now = _now()
    changed = 0

    for token in tokens:
        if token.expires_at > now:
            token.expires_at = now
            db.add(token)
            changed += 1

    return changed


@router.get("/users/{user_id}/verification-tokens")
def read_user_verification_tokens_as_admin(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    user = _get_user_or_404(db, user_id)

    tokens = (
        db.query(EmailVerificationToken)
        .filter(EmailVerificationToken.user_id == user.id)
        .order_by(EmailVerificationToken.created_at.desc())
        .limit(100)
        .all()
    )

    return {
        "service": "admin-auth",
        "user_id": str(user.id),
        "email": user.email,
        "email_verified": user.email_verified,
        "tokens": [_token_to_dict(token) for token in tokens],
    }


@router.post("/users/{user_id}/verify-email")
def verify_user_email_as_admin(
    user_id: UUID,
    payload: AdminAuthActionPayload | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    user = _get_user_or_404(db, user_id)

    previous_email_verified = bool(user.email_verified)
    reason = payload.reason if payload else None

    user.email_verified = True
    user.updated_at = _now()

    active_tokens = (
        db.query(EmailVerificationToken)
        .filter(
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.used_at.is_(None),
        )
        .all()
    )

    for token in active_tokens:
        token.used_at = token.used_at or _now()
        db.add(token)

    db.add(user)
    db.flush()

    add_user_email_verified_event_to_outbox(
        db,
        user=user,
    )

    _write_audit(
        db,
        actor_user_id=current_user.id,
        action="auth.verify_email",
        user=user,
        reason=reason,
        extra={
            "previous_email_verified": previous_email_verified,
            "new_email_verified": user.email_verified,
            "marked_tokens_used": len(active_tokens),
            "published_events": ["user.email_verified"],
        },
    )

    db.commit()
    db.refresh(user)

    return {
        "service": "admin-auth",
        "action": "auth.verify_email",
        "user_id": str(user.id),
        "email": user.email,
        "previous_email_verified": previous_email_verified,
        "email_verified": user.email_verified,
        "marked_tokens_used": len(active_tokens),
        "published_events": ["user.email_verified"],
        "reason": reason,
    }


@router.post("/users/{user_id}/unverify-email")
def unverify_user_email_as_admin(
    user_id: UUID,
    payload: AdminAuthActionPayload | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    user = _get_user_or_404(db, user_id)

    previous_email_verified = bool(user.email_verified)
    reason = payload.reason if payload else None

    user.email_verified = False
    user.updated_at = _now()

    expired_tokens = _expire_active_tokens(db, user_id=user.id)

    db.add(user)

    _write_audit(
        db,
        actor_user_id=current_user.id,
        action="auth.unverify_email",
        user=user,
        reason=reason,
        extra={
            "previous_email_verified": previous_email_verified,
            "new_email_verified": user.email_verified,
            "expired_tokens": expired_tokens,
        },
    )

    db.commit()
    db.refresh(user)

    return {
        "service": "admin-auth",
        "action": "auth.unverify_email",
        "user_id": str(user.id),
        "email": user.email,
        "previous_email_verified": previous_email_verified,
        "email_verified": user.email_verified,
        "expired_tokens": expired_tokens,
        "reason": reason,
    }


@router.post("/users/{user_id}/resend-verification")
def resend_user_verification_as_admin(
    user_id: UUID,
    payload: AdminResendVerificationPayload | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    user = _get_user_or_404(db, user_id)

    reason = payload.reason if payload else None
    expire_previous_tokens = payload.expire_previous_tokens if payload else True

    if user.email_verified:
        _write_audit(
            db,
            actor_user_id=current_user.id,
            action="auth.resend_verification_skipped",
            user=user,
            reason=reason,
            extra={
                "message": "Email already verified",
            },
        )

        db.commit()

        return {
            "service": "admin-auth",
            "action": "auth.resend_verification",
            "user_id": str(user.id),
            "email": user.email,
            "sent": False,
            "message": "Email is already verified",
            "reason": reason,
        }

    expired_tokens = 0

    if expire_previous_tokens:
        expired_tokens = _expire_active_tokens(db, user_id=user.id)

    token = EmailVerificationToken(
        user_id=user.id,
        token=uuid.uuid4().hex + uuid.uuid4().hex,
        expires_at=_now() + timedelta(hours=24),
    )

    db.add(token)

    _write_audit(
        db,
        actor_user_id=current_user.id,
        action="auth.resend_verification",
        user=user,
        reason=reason,
        extra={
            "expire_previous_tokens": expire_previous_tokens,
            "expired_tokens": expired_tokens,
            "new_token_id": str(token.id),
            "new_token_expires_at": token.expires_at.isoformat(),
        },
    )

    db.commit()
    db.refresh(token)

    send_verification_email(
        to_email=user.email,
        token=token.token,
    )

    return {
        "service": "admin-auth",
        "action": "auth.resend_verification",
        "user_id": str(user.id),
        "email": user.email,
        "sent": True,
        "expired_tokens": expired_tokens,
        "new_token_id": str(token.id),
        "new_token_expires_at": token.expires_at.isoformat(),
        "reason": reason,
    }


@router.post("/users/{user_id}/expire-verification-tokens")
def expire_user_verification_tokens_as_admin(
    user_id: UUID,
    payload: AdminAuthActionPayload | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    user = _get_user_or_404(db, user_id)
    reason = payload.reason if payload else None

    expired_tokens = _expire_active_tokens(db, user_id=user.id)

    _write_audit(
        db,
        actor_user_id=current_user.id,
        action="auth.expire_verification_tokens",
        user=user,
        reason=reason,
        extra={
            "expired_tokens": expired_tokens,
        },
    )

    db.commit()

    return {
        "service": "admin-auth",
        "action": "auth.expire_verification_tokens",
        "user_id": str(user.id),
        "email": user.email,
        "expired_tokens": expired_tokens,
        "reason": reason,
    }


@router.post("/users/{user_id}/activate")
def activate_user_as_admin(
    user_id: UUID,
    payload: AdminAuthActionPayload | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    user = _get_user_or_404(db, user_id)
    reason = payload.reason if payload else None

    previous_is_active = bool(user.is_active)

    user.is_active = True
    user.updated_at = _now()

    db.add(user)

    _write_audit(
        db,
        actor_user_id=current_user.id,
        action="auth.activate_user",
        user=user,
        reason=reason,
        extra={
            "previous_is_active": previous_is_active,
            "new_is_active": user.is_active,
        },
    )

    db.commit()
    db.refresh(user)

    return {
        "service": "admin-auth",
        "action": "auth.activate_user",
        "user_id": str(user.id),
        "email": user.email,
        "previous_is_active": previous_is_active,
        "is_active": user.is_active,
        "reason": reason,
    }


@router.post("/users/{user_id}/deactivate")
def deactivate_user_as_admin(
    user_id: UUID,
    payload: AdminAuthActionPayload | None = None,
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
    user.updated_at = _now()

    db.add(user)

    _write_audit(
        db,
        actor_user_id=current_user.id,
        action="auth.deactivate_user",
        user=user,
        reason=reason,
        extra={
            "previous_is_active": previous_is_active,
            "new_is_active": user.is_active,
        },
    )

    db.commit()
    db.refresh(user)

    return {
        "service": "admin-auth",
        "action": "auth.deactivate_user",
        "user_id": str(user.id),
        "email": user.email,
        "previous_is_active": previous_is_active,
        "is_active": user.is_active,
        "reason": reason,
    }