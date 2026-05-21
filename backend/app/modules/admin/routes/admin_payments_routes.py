from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.admin import require_admin
from app.events.order_events import (
    add_order_payment_expired_event_to_outbox,
    add_order_payment_failed_event_to_outbox,
)
from app.events.payment_events import (
    add_payment_expired_event_to_outbox,
    add_payment_failed_event_to_outbox,
)
from app.models.audit_log_event import AuditLogEvent
from app.modules.admin.schemas.admin_payments import (
    AdminPaymentActionPayload,
    AdminPaymentRetryCheckoutPayload,
)
from app.modules.orders.models.order import Order, OrderItem
from app.modules.payments.models.payment import (
    Payment,
    PaymentTransaction,
    StripeCheckoutSession,
    StripePaymentIntent,
)
from app.modules.users.models.user import User

router = APIRouter()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_payment_or_404(db: Session, payment_id: UUID) -> Payment:
    payment = db.query(Payment).filter(Payment.id == payment_id).first()

    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    return payment


def _get_order_or_404(db: Session, order_id: UUID) -> Order:
    order = db.query(Order).filter(Order.id == order_id).first()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    return order


def _set_order_items_status(
    db: Session,
    *,
    order_id: UUID,
    status: str,
) -> int:
    order_items = db.query(OrderItem).filter(OrderItem.order_id == order_id).all()
    changed = 0

    for order_item in order_items:
        if order_item.status != status:
            order_item.status = status
            order_item.updated_at = _now()
            db.add(order_item)
            changed += 1

    return changed


def _write_audit(
    db: Session,
    *,
    actor_user_id: UUID,
    action: str,
    payment: Payment,
    previous_payment_status: str,
    new_payment_status: str,
    order: Order | None,
    previous_order_status: str | None,
    new_order_status: str | None,
    reason: str | None,
    extra: dict[str, Any] | None = None,
) -> None:
    meta = {
        "payment_id": str(payment.id),
        "order_id": str(payment.order_id),
        "previous_payment_status": previous_payment_status,
        "new_payment_status": new_payment_status,
        "previous_order_status": previous_order_status,
        "new_order_status": new_order_status,
        "reason": reason,
    }

    if extra:
        meta.update(extra)

    db.add(
        AuditLogEvent(
            actor_user_id=actor_user_id,
            action=action,
            entity_type="Payment",
            entity_id=payment.id,
            meta=meta,
        )
    )


def _transaction_to_dict(transaction: PaymentTransaction) -> dict[str, Any]:
    return {
        "id": str(transaction.id),
        "payment_id": str(transaction.payment_id),
        "order_id": str(transaction.order_id),
        "provider": transaction.provider,
        "type": transaction.type,
        "status": transaction.status,
        "amount_cents": transaction.amount_cents,
        "currency": transaction.currency,
        "provider_tx_id": transaction.provider_tx_id,
        "error_message": transaction.error_message,
        "created_at": transaction.created_at.isoformat() if transaction.created_at else None,
    }


def _checkout_session_to_dict(session: StripeCheckoutSession) -> dict[str, Any]:
    return {
        "id": str(session.id),
        "payment_id": str(session.payment_id),
        "order_id": str(session.order_id),
        "user_id": str(session.user_id),
        "provider_session_id": session.provider_session_id,
        "status": session.status,
        "payment_status": session.payment_status,
        "checkout_url": session.checkout_url,
        "amount_total_cents": session.amount_total_cents,
        "currency": session.currency,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "updated_at": session.updated_at.isoformat() if session.updated_at else None,
        "completed_at": session.completed_at.isoformat() if session.completed_at else None,
        "expired_at": session.expired_at.isoformat() if session.expired_at else None,
        "expires_at": session.expires_at.isoformat() if session.expires_at else None,
    }


def _payment_intent_to_dict(intent: StripePaymentIntent) -> dict[str, Any]:
    return {
        "id": str(intent.id),
        "payment_id": str(intent.payment_id),
        "order_id": str(intent.order_id),
        "provider_payment_intent_id": intent.provider_payment_intent_id,
        "status": intent.status,
        "amount_cents": intent.amount_cents,
        "currency": intent.currency,
        "latest_charge_id": intent.latest_charge_id,
        "created_at": intent.created_at.isoformat() if intent.created_at else None,
        "updated_at": intent.updated_at.isoformat() if intent.updated_at else None,
        "succeeded_at": intent.succeeded_at.isoformat() if intent.succeeded_at else None,
        "canceled_at": intent.canceled_at.isoformat() if intent.canceled_at else None,
    }


def _payment_result(
    *,
    action: str,
    payment: Payment,
    order: Order,
    previous_payment_status: str,
    previous_order_status: str,
    changed_order_items: int,
    published_events: list[str],
    reason: str | None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = {
        "service": "admin-payments",
        "action": action,
        "payment_id": str(payment.id),
        "order_id": str(order.id),
        "previous_payment_status": previous_payment_status,
        "new_payment_status": payment.status,
        "previous_order_status": previous_order_status,
        "new_order_status": order.status,
        "changed_order_items": changed_order_items,
        "published_events": published_events,
        "reason": reason,
    }

    if extra:
        result.update(extra)

    return result


@router.get("/{payment_id}/transactions")
def read_payment_transactions_as_admin(
    payment_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    payment = _get_payment_or_404(db, payment_id)

    transactions = (
        db.query(PaymentTransaction)
        .filter(PaymentTransaction.payment_id == payment.id)
        .order_by(PaymentTransaction.created_at.desc())
        .all()
    )

    checkout_sessions = (
        db.query(StripeCheckoutSession)
        .filter(StripeCheckoutSession.payment_id == payment.id)
        .order_by(StripeCheckoutSession.created_at.desc())
        .all()
    )

    payment_intents = (
        db.query(StripePaymentIntent)
        .filter(StripePaymentIntent.payment_id == payment.id)
        .order_by(StripePaymentIntent.created_at.desc())
        .all()
    )

    return {
        "service": "admin-payments",
        "payment_id": str(payment.id),
        "order_id": str(payment.order_id),
        "payment_status": payment.status,
        "transactions": [_transaction_to_dict(transaction) for transaction in transactions],
        "checkout_sessions": [_checkout_session_to_dict(session) for session in checkout_sessions],
        "payment_intents": [_payment_intent_to_dict(intent) for intent in payment_intents],
    }


@router.post("/{payment_id}/mark-failed")
def mark_payment_failed_as_admin(
    payment_id: UUID,
    payload: AdminPaymentActionPayload | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    payment = _get_payment_or_404(db, payment_id)
    order = _get_order_or_404(db, payment.order_id)

    previous_payment_status = payment.status
    previous_order_status = order.status
    reason = payload.reason if payload else None
    now = _now()

    payment.status = "failed"
    payment.failed_at = payment.failed_at or now
    payment.updated_at = now

    order.status = "payment_failed"
    order.updated_at = now

    changed_order_items = _set_order_items_status(
        db,
        order_id=order.id,
        status="payment_failed",
    )

    transaction = PaymentTransaction(
        payment_id=payment.id,
        order_id=order.id,
        provider=payment.provider,
        type="admin_mark_failed",
        status="failed",
        amount_cents=payment.amount_total_cents,
        currency=payment.currency,
        error_message=reason,
    )

    db.add(payment)
    db.add(order)
    db.add(transaction)

    add_payment_failed_event_to_outbox(
        db,
        order=order,
        payment=payment,
        error_message=reason,
    )

    add_order_payment_failed_event_to_outbox(
        db,
        order=order,
        payment=payment,
        error_message=reason,
    )

    _write_audit(
        db,
        actor_user_id=current_user.id,
        action="payment.mark_failed",
        payment=payment,
        previous_payment_status=previous_payment_status,
        new_payment_status=payment.status,
        order=order,
        previous_order_status=previous_order_status,
        new_order_status=order.status,
        reason=reason,
        extra={
            "changed_order_items": changed_order_items,
            "published_events": ["payment.failed", "order.payment_failed"],
        },
    )

    db.commit()
    db.refresh(payment)

    return _payment_result(
        action="payment.mark_failed",
        payment=payment,
        order=order,
        previous_payment_status=previous_payment_status,
        previous_order_status=previous_order_status,
        changed_order_items=changed_order_items,
        published_events=["payment.failed", "order.payment_failed"],
        reason=reason,
    )


@router.post("/{payment_id}/mark-expired")
def mark_payment_expired_as_admin(
    payment_id: UUID,
    payload: AdminPaymentActionPayload | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    payment = _get_payment_or_404(db, payment_id)
    order = _get_order_or_404(db, payment.order_id)

    previous_payment_status = payment.status
    previous_order_status = order.status
    reason = payload.reason if payload else None
    now = _now()

    payment.status = "expired"
    payment.cancelled_at = payment.cancelled_at or now
    payment.updated_at = now

    order.status = "payment_expired"
    order.updated_at = now

    changed_order_items = _set_order_items_status(
        db,
        order_id=order.id,
        status="payment_expired",
    )

    open_sessions = (
        db.query(StripeCheckoutSession)
        .filter(
            StripeCheckoutSession.payment_id == payment.id,
            StripeCheckoutSession.status.in_(["open", "creating"]),
        )
        .all()
    )

    for session in open_sessions:
        session.status = "expired"
        session.expired_at = session.expired_at or now
        session.updated_at = now
        db.add(session)

    transaction = PaymentTransaction(
        payment_id=payment.id,
        order_id=order.id,
        provider=payment.provider,
        type="admin_mark_expired",
        status="expired",
        amount_cents=payment.amount_total_cents,
        currency=payment.currency,
        error_message=reason,
    )

    db.add(payment)
    db.add(order)
    db.add(transaction)

    add_payment_expired_event_to_outbox(
        db,
        order=order,
        payment=payment,
    )

    add_order_payment_expired_event_to_outbox(
        db,
        order=order,
        payment=payment,
    )

    _write_audit(
        db,
        actor_user_id=current_user.id,
        action="payment.mark_expired",
        payment=payment,
        previous_payment_status=previous_payment_status,
        new_payment_status=payment.status,
        order=order,
        previous_order_status=previous_order_status,
        new_order_status=order.status,
        reason=reason,
        extra={
            "changed_order_items": changed_order_items,
            "expired_checkout_sessions": len(open_sessions),
            "published_events": ["payment.expired", "order.payment_expired"],
        },
    )

    db.commit()
    db.refresh(payment)

    return _payment_result(
        action="payment.mark_expired",
        payment=payment,
        order=order,
        previous_payment_status=previous_payment_status,
        previous_order_status=previous_order_status,
        changed_order_items=changed_order_items,
        published_events=["payment.expired", "order.payment_expired"],
        reason=reason,
        extra={
            "expired_checkout_sessions": len(open_sessions),
        },
    )


@router.post("/{payment_id}/mark-refunded")
def mark_payment_refunded_as_admin(
    payment_id: UUID,
    payload: AdminPaymentActionPayload | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    payment = _get_payment_or_404(db, payment_id)
    order = _get_order_or_404(db, payment.order_id)

    previous_payment_status = payment.status
    previous_order_status = order.status
    reason = payload.reason if payload else None
    now = _now()

    payment.status = "refunded"
    payment.updated_at = now

    transaction = PaymentTransaction(
        payment_id=payment.id,
        order_id=order.id,
        provider=payment.provider,
        type="admin_mark_refunded",
        status="success",
        amount_cents=payment.amount_total_cents,
        currency=payment.currency,
        provider_tx_id=payment.stripe_payment_intent_id,
        error_message=reason,
    )

    db.add(payment)
    db.add(transaction)

    _write_audit(
        db,
        actor_user_id=current_user.id,
        action="payment.mark_refunded",
        payment=payment,
        previous_payment_status=previous_payment_status,
        new_payment_status=payment.status,
        order=order,
        previous_order_status=previous_order_status,
        new_order_status=order.status,
        reason=reason,
        extra={
            "note": "This action marks local payment state as refunded. It does not call Stripe refund API.",
            "provider_tx_id": payment.stripe_payment_intent_id,
        },
    )

    db.commit()
    db.refresh(payment)

    return _payment_result(
        action="payment.mark_refunded",
        payment=payment,
        order=order,
        previous_payment_status=previous_payment_status,
        previous_order_status=previous_order_status,
        changed_order_items=0,
        published_events=[],
        reason=reason,
        extra={
            "note": "Local status changed only. Stripe refund API was not called.",
        },
    )


@router.post("/{payment_id}/retry-checkout")
def retry_payment_checkout_as_admin(
    payment_id: UUID,
    payload: AdminPaymentRetryCheckoutPayload | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    payment = _get_payment_or_404(db, payment_id)
    order = _get_order_or_404(db, payment.order_id)

    previous_payment_status = payment.status
    previous_order_status = order.status
    reason = payload.reason if payload else None
    clear_stripe_references = payload.clear_stripe_references if payload else True
    now = _now()

    if payment.status == "paid":
        raise HTTPException(
            status_code=400,
            detail="Paid payment cannot be retried",
        )

    order.status = "awaiting_payment"
    order.updated_at = now

    payment.status = "pending"
    payment.failed_at = None
    payment.cancelled_at = None
    payment.updated_at = now

    if clear_stripe_references:
        payment.stripe_checkout_session_id = None
        payment.stripe_payment_intent_id = None
        order.stripe_checkout_session_id = None
        order.stripe_payment_intent_id = None

    changed_order_items = _set_order_items_status(
        db,
        order_id=order.id,
        status="awaiting_payment",
    )

    open_sessions = (
        db.query(StripeCheckoutSession)
        .filter(
            StripeCheckoutSession.payment_id == payment.id,
            StripeCheckoutSession.status.in_(["open", "creating"]),
        )
        .all()
    )

    for session in open_sessions:
        session.status = "expired"
        session.expired_at = session.expired_at or now
        session.updated_at = now
        db.add(session)

    transaction = PaymentTransaction(
        payment_id=payment.id,
        order_id=order.id,
        provider=payment.provider,
        type="admin_retry_checkout",
        status="success",
        amount_cents=payment.amount_total_cents,
        currency=payment.currency,
        error_message=reason,
    )

    db.add(payment)
    db.add(order)
    db.add(transaction)

    _write_audit(
        db,
        actor_user_id=current_user.id,
        action="payment.retry_checkout",
        payment=payment,
        previous_payment_status=previous_payment_status,
        new_payment_status=payment.status,
        order=order,
        previous_order_status=previous_order_status,
        new_order_status=order.status,
        reason=reason,
        extra={
            "changed_order_items": changed_order_items,
            "expired_checkout_sessions": len(open_sessions),
            "clear_stripe_references": clear_stripe_references,
            "next_step": f"POST /api/v1/orders/{order.id}/checkout-session",
        },
    )

    db.commit()
    db.refresh(payment)

    return _payment_result(
        action="payment.retry_checkout",
        payment=payment,
        order=order,
        previous_payment_status=previous_payment_status,
        previous_order_status=previous_order_status,
        changed_order_items=changed_order_items,
        published_events=[],
        reason=reason,
        extra={
            "expired_checkout_sessions": len(open_sessions),
            "clear_stripe_references": clear_stripe_references,
            "next_step": f"POST /api/v1/orders/{order.id}/checkout-session",
        },
    )