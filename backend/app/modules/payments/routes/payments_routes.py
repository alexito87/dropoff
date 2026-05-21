from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.admin import require_admin
from app.modules.payments.models.payment import (
    Payment,
    PaymentTransaction,
    StripeCheckoutSession,
    StripePaymentIntent,
)
from app.modules.users.models.user import User

router = APIRouter()


def _payment_to_dict(payment: Payment) -> dict:
    return {
        "id": str(payment.id),
        "order_id": str(payment.order_id),
        "payer_user_id": str(payment.payer_user_id),
        "status": payment.status,
        "provider": payment.provider,
        "payment_method": payment.payment_method,
        "amount_total_cents": payment.amount_total_cents,
        "currency": payment.currency,
        "stripe_checkout_session_id": payment.stripe_checkout_session_id,
        "stripe_payment_intent_id": payment.stripe_payment_intent_id,
        "created_at": payment.created_at.isoformat() if payment.created_at else None,
        "updated_at": payment.updated_at.isoformat() if payment.updated_at else None,
        "paid_at": payment.paid_at.isoformat() if payment.paid_at else None,
        "failed_at": payment.failed_at.isoformat() if payment.failed_at else None,
        "cancelled_at": payment.cancelled_at.isoformat() if payment.cancelled_at else None,
    }


def _transaction_to_dict(transaction: PaymentTransaction) -> dict:
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


def _checkout_session_to_dict(session: StripeCheckoutSession) -> dict:
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


def _payment_intent_to_dict(intent: StripePaymentIntent) -> dict:
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


def _payment_details(db: Session, payment: Payment) -> dict:
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
        **_payment_to_dict(payment),
        "transactions": [_transaction_to_dict(transaction) for transaction in transactions],
        "checkout_sessions": [_checkout_session_to_dict(session) for session in checkout_sessions],
        "payment_intents": [_payment_intent_to_dict(intent) for intent in payment_intents],
    }


@router.get("/admin")
def read_all_payments_as_admin(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    payments = (
        db.query(Payment)
        .order_by(Payment.updated_at.desc())
        .limit(200)
        .all()
    )

    return {
        "payments": [_payment_to_dict(payment) for payment in payments],
    }


@router.get("/{payment_id}")
def read_payment_as_admin(
    payment_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    payment = db.query(Payment).filter(Payment.id == payment_id).first()

    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    return _payment_details(db, payment)


@router.get("/order/{order_id}")
def read_order_payments_as_admin(
    order_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    payments = (
        db.query(Payment)
        .filter(Payment.order_id == order_id)
        .order_by(Payment.created_at.desc())
        .all()
    )

    return {
        "order_id": str(order_id),
        "payments": [_payment_details(db, payment) for payment in payments],
    }
