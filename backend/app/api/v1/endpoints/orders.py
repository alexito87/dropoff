from datetime import datetime, timezone
from uuid import UUID

import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.models.cart import Cart, CartItem
from app.models.item import Item
from app.models.notification import Notification
from app.models.order import Order, OrderItem
from app.models.payment import Payment, PaymentTransaction, StripeCheckoutSession, StripePaymentIntent
from app.models.user import User
from app.schemas.order import (
    CheckoutSessionRead,
    OrderCreate,
    OrderItemRead,
    OrderRead,
    PaymentRead,
    StripePaymentConfirm,
)

router = APIRouter()

DELIVERY_METHODS = {
    "pickup": 0,
    "courier_standard": 1200,
}

SUPPORTED_PAYMENT_METHODS = {"stripe_checkout"}
PAYMENT_TERMINAL_STATUSES = {"paid", "failed", "cancelled", "expired", "refunded"}


def _now():
    return datetime.now(timezone.utc)


def _days_count(start_date, end_date) -> int:
    return (end_date - start_date).days + 1


def _stripe_dt(timestamp_value):
    if not timestamp_value:
        return None
    return datetime.fromtimestamp(int(timestamp_value), tz=timezone.utc)


def _create_notification(db: Session, user_id, notification_type: str, payload: dict):
    db.add(
        Notification(
            user_id=user_id,
            type=notification_type,
            payload=payload,
        )
    )


def _add_transaction(
    db: Session,
    payment: Payment,
    tx_type: str,
    tx_status: str,
    provider_tx_id: str | None = None,
    error_message: str | None = None,
) -> PaymentTransaction:
    transaction = PaymentTransaction(
        payment_id=payment.id,
        order_id=payment.order_id,
        provider=payment.provider,
        type=tx_type,
        status=tx_status,
        amount_cents=payment.amount_total_cents,
        currency=payment.currency,
        provider_tx_id=provider_tx_id,
        error_message=error_message,
    )
    db.add(transaction)
    return transaction


def _payment_to_read(payment: Payment | None) -> PaymentRead | None:
    if not payment:
        return None
    return PaymentRead(
        id=payment.id,
        status=payment.status,
        provider=payment.provider,
        payment_method=payment.payment_method,
        amount_total_cents=payment.amount_total_cents,
        currency=payment.currency,
        stripe_checkout_session_id=payment.stripe_checkout_session_id,
        stripe_payment_intent_id=payment.stripe_payment_intent_id,
        created_at=payment.created_at,
        updated_at=payment.updated_at,
        paid_at=payment.paid_at,
        failed_at=payment.failed_at,
        cancelled_at=payment.cancelled_at,
    )


def _get_order_payment(db: Session, order_id: UUID) -> Payment | None:
    return (
        db.query(Payment)
        .filter(Payment.order_id == order_id)
        .order_by(Payment.created_at.desc())
        .first()
    )


def _payment_transaction_exists(
    db: Session,
    payment_id: UUID,
    tx_type: str,
    provider_tx_id: str | None,
) -> bool:
    if not provider_tx_id:
        return False

    return (
        db.query(PaymentTransaction)
        .filter(
            PaymentTransaction.payment_id == payment_id,
            PaymentTransaction.type == tx_type,
            PaymentTransaction.provider_tx_id == provider_tx_id,
        )
        .first()
        is not None
    )


def _order_item_to_read(db: Session, order_item: OrderItem) -> OrderItemRead:
    item = db.query(Item).filter(Item.id == order_item.item_id).first()
    owner = db.query(User).filter(User.id == order_item.owner_id).first()

    return OrderItemRead(
        id=order_item.id,
        item_id=order_item.item_id,
        item_title=item.title if item else "",
        owner_id=order_item.owner_id,
        owner_name=owner.full_name if owner else None,
        rent_start=order_item.rent_start,
        rent_end=order_item.rent_end,
        days_count=_days_count(order_item.rent_start, order_item.rent_end),
        quantity=order_item.quantity,
        daily_price_cents=order_item.daily_price_cents,
        deposit_cents=order_item.deposit_cents,
        rent_total_cents=order_item.rent_total_cents,
        total_deposit_cents=order_item.total_deposit_cents,
        line_total_cents=order_item.line_total_cents,
        status=order_item.status,
    )


def _order_to_read(db: Session, order: Order) -> OrderRead:
    order_items = (
        db.query(OrderItem)
        .filter(OrderItem.order_id == order.id)
        .order_by(OrderItem.created_at.asc())
        .all()
    )
    payment = _get_order_payment(db, order.id)

    return OrderRead(
        id=order.id,
        status=order.status,
        delivery_method=order.delivery_method,
        payment_method=order.payment_method,
        items_total_cents=order.items_total_cents,
        deposit_total_cents=order.deposit_total_cents,
        delivery_fee_cents=order.delivery_fee_cents,
        total_amount_cents=order.total_amount_cents,
        stripe_checkout_session_id=order.stripe_checkout_session_id,
        stripe_payment_intent_id=order.stripe_payment_intent_id,
        payment=_payment_to_read(payment),
        items=[_order_item_to_read(db, item) for item in order_items],
        created_at=order.created_at,
        updated_at=order.updated_at,
        paid_at=order.paid_at,
    )


def _build_stripe_line_items(db: Session, order: Order) -> list[dict]:
    order_items = (
        db.query(OrderItem)
        .filter(OrderItem.order_id == order.id)
        .order_by(OrderItem.created_at.asc())
        .all()
    )

    line_items: list[dict] = []
    for order_item in order_items:
        item = db.query(Item).filter(Item.id == order_item.item_id).first()
        item_title = item.title if item else f"Item {order_item.item_id}"
        days_count = _days_count(order_item.rent_start, order_item.rent_end)

        line_items.append(
            {
                "price_data": {
                    "currency": settings.stripe_currency,
                    "unit_amount": order_item.line_total_cents,
                    "product_data": {
                        "name": item_title,
                        "description": (
                            f"Аренда {days_count} дн.: {order_item.rent_start} — {order_item.rent_end}. "
                            f"Включая депозит: {order_item.total_deposit_cents / 100:.2f} {settings.stripe_currency.upper()}"
                        ),
                    },
                },
                "quantity": order_item.quantity,
            }
        )

    if order.delivery_fee_cents > 0:
        line_items.append(
            {
                "price_data": {
                    "currency": settings.stripe_currency,
                    "unit_amount": order.delivery_fee_cents,
                    "product_data": {
                        "name": "Доставка",
                        "description": order.delivery_method,
                    },
                },
                "quantity": 1,
            }
        )

    return line_items


def _stripe_value(obj, key, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _get_payment_intent_id(stripe_session) -> str | None:
    payment_intent = _stripe_value(stripe_session, "payment_intent")
    if not payment_intent:
        return None
    if isinstance(payment_intent, str):
        return payment_intent
    return _stripe_value(payment_intent, "id")


def _get_payment_intent_status(stripe_session) -> str | None:
    payment_intent = _stripe_value(stripe_session, "payment_intent")
    if not payment_intent or isinstance(payment_intent, str):
        return None
    return _stripe_value(payment_intent, "status")


def _get_payment_intent_amount(stripe_session) -> int:
    payment_intent = _stripe_value(stripe_session, "payment_intent")
    if payment_intent and not isinstance(payment_intent, str):
        return int(_stripe_value(payment_intent, "amount", 0) or 0)
    return int(_stripe_value(stripe_session, "amount_total", 0) or 0)


def _get_payment_intent_currency(stripe_session) -> str:
    payment_intent = _stripe_value(stripe_session, "payment_intent")
    if payment_intent and not isinstance(payment_intent, str):
        return _stripe_value(payment_intent, "currency", settings.stripe_currency)
    return _stripe_value(stripe_session, "currency", settings.stripe_currency)


def _get_latest_charge_id(stripe_session) -> str | None:
    payment_intent = _stripe_value(stripe_session, "payment_intent")
    if not payment_intent or isinstance(payment_intent, str):
        return None
    latest_charge = _stripe_value(payment_intent, "latest_charge")
    if isinstance(latest_charge, str):
        return latest_charge
    return _stripe_value(latest_charge, "id")


def _sync_stripe_session_state(
    db: Session,
    order: Order,
    payment: Payment,
    stripe_session,
    tx_type: str,
) -> None:
    provider_session_id = _stripe_value(stripe_session, "id")
    session_status = _stripe_value(stripe_session, "status", "unknown") or "unknown"
    payment_status = _stripe_value(stripe_session, "payment_status", "unpaid") or "unpaid"
    payment_intent_id = _get_payment_intent_id(stripe_session)
    now = _now()

    checkout_session = (
        db.query(StripeCheckoutSession)
        .filter(StripeCheckoutSession.provider_session_id == provider_session_id)
        .first()
    )
    if not checkout_session:
        checkout_session = StripeCheckoutSession(
            payment_id=payment.id,
            order_id=order.id,
            user_id=order.user_id,
            provider_session_id=provider_session_id,
            amount_total_cents=int(_stripe_value(stripe_session, "amount_total", payment.amount_total_cents) or payment.amount_total_cents),
            currency=_stripe_value(stripe_session, "currency", payment.currency) or payment.currency,
        )
        db.add(checkout_session)

    checkout_session.status = session_status
    checkout_session.payment_status = payment_status
    checkout_session.checkout_url = _stripe_value(stripe_session, "url") or checkout_session.checkout_url
    checkout_session.amount_total_cents = int(_stripe_value(stripe_session, "amount_total", checkout_session.amount_total_cents) or checkout_session.amount_total_cents)
    checkout_session.currency = _stripe_value(stripe_session, "currency", checkout_session.currency) or checkout_session.currency
    checkout_session.expires_at = _stripe_dt(_stripe_value(stripe_session, "expires_at"))
    checkout_session.updated_at = now
    if session_status == "complete":
        checkout_session.completed_at = checkout_session.completed_at or now
    if session_status == "expired":
        checkout_session.expired_at = checkout_session.expired_at or now

    payment.stripe_checkout_session_id = provider_session_id
    order.stripe_checkout_session_id = provider_session_id

    if payment_intent_id:
        payment.stripe_payment_intent_id = payment_intent_id
        order.stripe_payment_intent_id = payment_intent_id
        intent_status = _get_payment_intent_status(stripe_session) or "unknown"
        payment_intent = (
            db.query(StripePaymentIntent)
            .filter(StripePaymentIntent.provider_payment_intent_id == payment_intent_id)
            .first()
        )
        if not payment_intent:
            payment_intent = StripePaymentIntent(
                payment_id=payment.id,
                order_id=order.id,
                provider_payment_intent_id=payment_intent_id,
                status=intent_status,
                amount_cents=_get_payment_intent_amount(stripe_session),
                currency=_get_payment_intent_currency(stripe_session),
            )
            db.add(payment_intent)
        else:
            payment_intent.status = intent_status
            payment_intent.amount_cents = _get_payment_intent_amount(stripe_session)
            payment_intent.currency = _get_payment_intent_currency(stripe_session)
            payment_intent.updated_at = now

        payment_intent.latest_charge_id = _get_latest_charge_id(stripe_session)
        if intent_status == "succeeded":
            payment_intent.succeeded_at = payment_intent.succeeded_at or now
        if intent_status == "canceled":
            payment_intent.canceled_at = payment_intent.canceled_at or now

    if payment_status == "paid":
        order.status = "paid"
        order.paid_at = order.paid_at or now
        payment.status = "paid"
        payment.paid_at = payment.paid_at or now

        order_items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
        for order_item in order_items:
            order_item.status = "paid"
            order_item.updated_at = now
            db.add(order_item)

        _create_notification(
            db,
            order.user_id,
            "payment_success",
            {
                "order_id": str(order.id),
                "payment_id": str(payment.id),
                "status": payment.status,
                "total_amount_cents": order.total_amount_cents,
                "provider": "stripe",
            },
        )
    elif session_status == "expired":
        order.status = "payment_expired"
        payment.status = "expired"
        payment.cancelled_at = payment.cancelled_at or now
    elif payment_status == "unpaid" and session_status == "complete":
        order.status = "payment_failed"
        payment.status = "failed"
        payment.failed_at = payment.failed_at or now
    else:
        if payment.status not in PAYMENT_TERMINAL_STATUSES:
            payment.status = "processing"

    order.updated_at = now
    payment.updated_at = now
    db.add(order)
    db.add(payment)
    db.add(checkout_session)

    _add_transaction(
        db,
        payment,
        tx_type=tx_type,
        tx_status="success" if payment.status == "paid" else "pending",
        provider_tx_id=payment_intent_id or provider_session_id,
    )


@router.post("", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
def create_order_from_cart(
    payload: OrderCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.delivery_method not in DELIVERY_METHODS:
        raise HTTPException(status_code=400, detail="Unsupported delivery method")

    if payload.payment_method not in SUPPORTED_PAYMENT_METHODS:
        raise HTTPException(status_code=400, detail="For MVP only stripe_checkout is supported")

    try:
        cart = (
            db.query(Cart)
            .filter(Cart.user_id == current_user.id, Cart.status == "active")
            .with_for_update()
            .first()
        )
        if not cart:
            raise HTTPException(status_code=400, detail="Active cart is empty")

        cart_items = (
            db.query(CartItem)
            .filter(CartItem.cart_id == cart.id)
            .order_by(CartItem.created_at.asc())
            .all()
        )
        if not cart_items:
            raise HTTPException(status_code=400, detail="Active cart is empty")

        items_total = sum(item.rent_total_cents for item in cart_items)
        deposit_total = sum(item.total_deposit_cents for item in cart_items)
        delivery_fee = DELIVERY_METHODS[payload.delivery_method]
        total_amount = items_total + deposit_total + delivery_fee
        now = _now()

        order = Order(
            user_id=current_user.id,
            cart_id=cart.id,
            status="awaiting_payment",
            delivery_method=payload.delivery_method,
            payment_method=payload.payment_method,
            items_total_cents=items_total,
            deposit_total_cents=deposit_total,
            delivery_fee_cents=delivery_fee,
            total_amount_cents=total_amount,
            created_at=now,
            updated_at=now,
        )
        db.add(order)
        db.flush()

        payment = Payment(
            order_id=order.id,
            payer_user_id=current_user.id,
            status="pending",
            provider="stripe",
            payment_method=payload.payment_method,
            amount_total_cents=total_amount,
            currency=settings.stripe_currency,
            created_at=now,
            updated_at=now,
        )
        db.add(payment)
        db.flush()

        owner_ids = set()
        for cart_item in cart_items:
            item = db.query(Item).filter(Item.id == cart_item.item_id).first()
            if not item:
                raise HTTPException(status_code=400, detail="One of cart items no longer exists")

            owner_ids.add(item.owner_id)
            db.add(
                OrderItem(
                    order_id=order.id,
                    item_id=item.id,
                    owner_id=item.owner_id,
                    rent_start=cart_item.rent_start,
                    rent_end=cart_item.rent_end,
                    quantity=cart_item.quantity,
                    status="awaiting_payment",
                    daily_price_cents=cart_item.daily_price_cents,
                    deposit_cents=cart_item.deposit_cents,
                    rent_total_cents=cart_item.rent_total_cents,
                    total_deposit_cents=cart_item.total_deposit_cents,
                    line_total_cents=cart_item.rent_total_cents + cart_item.total_deposit_cents,
                    created_at=now,
                    updated_at=now,
                )
            )

        cart.status = "converted"
        cart.updated_at = now
        db.add(cart)

        _add_transaction(db, payment, tx_type="payment_created", tx_status="success")

        _create_notification(
            db,
            current_user.id,
            "order_created",
            {"order_id": str(order.id), "payment_id": str(payment.id), "status": order.status, "total_amount_cents": total_amount},
        )

        for owner_id in owner_ids:
            _create_notification(
                db,
                owner_id,
                "booking_created",
                {"order_id": str(order.id), "status": order.status},
            )

        db.commit()
        db.refresh(order)
        return _order_to_read(db, order)
    except Exception:
        db.rollback()
        raise


@router.get("/me", response_model=list[OrderRead])
def read_my_orders(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    orders = (
        db.query(Order)
        .filter(Order.user_id == current_user.id)
        .order_by(Order.created_at.desc())
        .all()
    )
    return [_order_to_read(db, order) for order in orders]


@router.post("/stripe/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(default=None, alias="stripe-signature"),
    db: Session = Depends(get_db),
):
    """
    Stripe webhook endpoint.

    Важно:
    - этот endpoint должен вызываться Stripe CLI или Stripe Dashboard;
    - обновление нашей БД происходит в одной локальной DB-транзакции;
    - повторный webhook не должен ломать состояние, потому что синхронизация идемпотентна.
    """
    if not settings.stripe_webhook_secret:
        raise HTTPException(status_code=400, detail="Stripe webhook secret is not configured")

    payload = await request.body()

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=stripe_signature,
            secret=settings.stripe_webhook_secret,
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid Stripe webhook payload")
    except stripe.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid Stripe webhook signature")

    event_type = _stripe_value(event, "type")
    event_id = _stripe_value(event, "id")

    if event_type not in {"checkout.session.completed", "checkout.session.expired"}:
        return {"received": True, "ignored": True, "event_type": event_type}

    event_data = _stripe_value(event, "data", {}) or {}
    raw_session = _stripe_value(event_data, "object")
    raw_metadata = _stripe_value(raw_session, "metadata", {}) or {}
    order_id = raw_metadata.get("order_id") if isinstance(raw_metadata, dict) else _stripe_value(raw_metadata, "order_id")
    provider_session_id = _stripe_value(raw_session, "id")

    if not order_id or not provider_session_id:
        return {"received": True, "ignored": True, "reason": "missing order_id or session_id"}

    if not settings.stripe_secret_key:
        raise HTTPException(status_code=500, detail="STRIPE_SECRET_KEY is not configured")

    stripe.api_key = settings.stripe_secret_key

    try:
        stripe_session = stripe.checkout.Session.retrieve(
            provider_session_id,
            expand=["payment_intent"],
        )
    except stripe.StripeError as exc:
        raise HTTPException(status_code=502, detail=f"Stripe error: {str(exc)}")

    try:
        order_uuid = UUID(str(order_id))
    except ValueError:
        return {"received": True, "ignored": True, "reason": "invalid order_id"}

    try:
        order = (
            db.query(Order)
            .filter(Order.id == order_uuid)
            .with_for_update()
            .first()
        )
        if not order:
            return {"received": True, "ignored": True, "reason": "order not found"}

        payment = _get_order_payment(db, order.id)
        if not payment:
            return {"received": True, "ignored": True, "reason": "payment not found"}

        if _payment_transaction_exists(db, payment.id, event_type, event_id):
            return {"received": True, "duplicate": True, "event_id": event_id}

        _sync_stripe_session_state(
            db,
            order,
            payment,
            stripe_session,
            tx_type=event_type,
        )

        if event_id:
            _add_transaction(
                db,
                payment,
                tx_type=event_type,
                tx_status="success",
                provider_tx_id=event_id,
            )

        db.commit()
    except Exception:
        db.rollback()
        raise

    return {"received": True, "event_type": event_type}


@router.get("/paid-rentals/me", response_model=list[OrderRead])
def read_my_paid_rentals(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    orders = (
        db.query(Order)
        .filter(Order.user_id == current_user.id, Order.status == "paid")
        .order_by(Order.paid_at.desc().nullslast(), Order.created_at.desc())
        .all()
    )
    return [_order_to_read(db, order) for order in orders]


@router.get("/paid-rentals/owner", response_model=list[OrderRead])
def read_owner_paid_rentals(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    orders = (
        db.query(Order)
        .join(OrderItem, OrderItem.order_id == Order.id)
        .filter(OrderItem.owner_id == current_user.id, Order.status == "paid")
        .distinct(Order.id)
        .order_by(Order.id, Order.paid_at.desc().nullslast(), Order.created_at.desc())
        .all()
    )
    return [_order_to_read(db, order) for order in orders]


@router.get("/{order_id}", response_model=OrderRead)
def read_order(
    order_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = db.query(Order).filter(Order.id == order_id, Order.user_id == current_user.id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return _order_to_read(db, order)


@router.post("/{order_id}/checkout-session", response_model=CheckoutSessionRead)
def create_checkout_session(
    order_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not settings.stripe_secret_key:
        raise HTTPException(status_code=500, detail="STRIPE_SECRET_KEY is not configured")

    order = (
        db.query(Order)
        .filter(Order.id == order_id, Order.user_id == current_user.id)
        .with_for_update()
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.status != "awaiting_payment":
        raise HTTPException(status_code=400, detail="Only awaiting_payment order can be paid")

    payment = _get_order_payment(db, order.id)
    if not payment:
        raise HTTPException(status_code=500, detail="Payment was not created for this order")

    if payment.status in PAYMENT_TERMINAL_STATUSES:
        raise HTTPException(status_code=400, detail=f"Payment is already {payment.status}")

    existing_open_session = (
        db.query(StripeCheckoutSession)
        .filter(
            StripeCheckoutSession.payment_id == payment.id,
            StripeCheckoutSession.status == "open",
            StripeCheckoutSession.checkout_url.isnot(None),
        )
        .order_by(StripeCheckoutSession.created_at.desc())
        .first()
    )
    if existing_open_session:
        return CheckoutSessionRead(
            order_id=order.id,
            payment_id=payment.id,
            checkout_url=existing_open_session.checkout_url,
            stripe_checkout_session_id=existing_open_session.provider_session_id,
            local_checkout_session_id=existing_open_session.id,
        )

    now = _now()
    local_session = StripeCheckoutSession(
        payment_id=payment.id,
        order_id=order.id,
        user_id=current_user.id,
        status="creating",
        payment_status="unpaid",
        amount_total_cents=payment.amount_total_cents,
        currency=payment.currency,
        created_at=now,
        updated_at=now,
    )
    payment.status = "checkout_creating"
    payment.updated_at = now
    _add_transaction(db, payment, tx_type="checkout_session_create_requested", tx_status="pending")
    db.add(local_session)
    db.add(payment)
    db.commit()

    stripe.api_key = settings.stripe_secret_key
    success_url = f"{settings.frontend_url}/orders/{order.id}/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{settings.frontend_url}/checkout?cancelled=1"

    try:
        stripe_session = stripe.checkout.Session.create(
            mode="payment",
            payment_method_types=["card"],
            line_items=_build_stripe_line_items(db, order),
            customer_email=current_user.email,
            client_reference_id=str(order.id),
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "order_id": str(order.id),
                "payment_id": str(payment.id),
                "user_id": str(current_user.id),
            },
            payment_intent_data={
                "metadata": {
                    "order_id": str(order.id),
                    "payment_id": str(payment.id),
                    "user_id": str(current_user.id),
                }
            },
            idempotency_key=f"dropoff-checkout-session-{order.id}-{payment.id}",
        )
    except stripe.StripeError as exc:
        order = db.query(Order).filter(Order.id == order_id).with_for_update().first()
        payment = _get_order_payment(db, order_id)
        local_session = db.query(StripeCheckoutSession).filter(StripeCheckoutSession.id == local_session.id).first()
        if payment:
            payment.status = "failed"
            payment.failed_at = _now()
            payment.updated_at = _now()
            _add_transaction(db, payment, tx_type="checkout_session_create_failed", tx_status="failed", error_message=str(exc))
            db.add(payment)
        if order:
            order.status = "payment_failed"
            order.updated_at = _now()
            db.add(order)
        if local_session:
            local_session.status = "failed"
            local_session.updated_at = _now()
            db.add(local_session)
        db.commit()
        raise HTTPException(status_code=502, detail=f"Stripe error: {str(exc)}")

    order = db.query(Order).filter(Order.id == order_id).with_for_update().first()
    payment = _get_order_payment(db, order_id)
    local_session = db.query(StripeCheckoutSession).filter(StripeCheckoutSession.id == local_session.id).first()
    now = _now()

    local_session.provider_session_id = stripe_session.id
    local_session.status = getattr(stripe_session, "status", None) or "open"
    local_session.payment_status = _stripe_value(stripe_session, "payment_status", "unpaid") or "unpaid"
    local_session.checkout_url = _stripe_value(stripe_session, "url")
    local_session.expires_at = _stripe_dt(_stripe_value(stripe_session, "expires_at"))
    local_session.updated_at = now

    payment.status = "checkout_created"
    payment.stripe_checkout_session_id = stripe_session.id
    payment.updated_at = now

    order.stripe_checkout_session_id = stripe_session.id
    order.updated_at = now

    _add_transaction(db, payment, tx_type="checkout_session_created", tx_status="success", provider_tx_id=stripe_session.id)
    db.add(local_session)
    db.add(payment)
    db.add(order)
    db.commit()

    return CheckoutSessionRead(
        order_id=order.id,
        payment_id=payment.id,
        checkout_url=stripe_session.url,
        stripe_checkout_session_id=stripe_session.id,
        local_checkout_session_id=local_session.id,
    )


@router.post("/{order_id}/stripe/confirm", response_model=OrderRead)
def confirm_stripe_payment(
    order_id: UUID,
    payload: StripePaymentConfirm,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not settings.stripe_secret_key:
        raise HTTPException(status_code=500, detail="STRIPE_SECRET_KEY is not configured")

    order = (
        db.query(Order)
        .filter(Order.id == order_id, Order.user_id == current_user.id)
        .with_for_update()
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    payment = _get_order_payment(db, order.id)
    if not payment:
        raise HTTPException(status_code=500, detail="Payment was not created for this order")

    stripe.api_key = settings.stripe_secret_key

    try:
        stripe_session = stripe.checkout.Session.retrieve(payload.stripe_checkout_session_id, expand=["payment_intent"])
    except stripe.StripeError as exc:
        _add_transaction(db, payment, tx_type="checkout_session_retrieve_failed", tx_status="failed", error_message=str(exc))
        db.commit()
        raise HTTPException(status_code=502, detail=f"Stripe error: {str(exc)}")

    stripe_metadata = _stripe_value(stripe_session, "metadata", {}) or {}
    stripe_order_id = stripe_metadata.get("order_id") if isinstance(stripe_metadata, dict) else _stripe_value(stripe_metadata, "order_id")
    if stripe_order_id != str(order.id):
        raise HTTPException(status_code=400, detail="Stripe session does not belong to this order")

    _sync_stripe_session_state(db, order, payment, stripe_session, tx_type="checkout_session_confirmed")
    db.commit()
    db.refresh(order)
    return _order_to_read(db, order)


@router.post("/{order_id}/sandbox-pay", response_model=OrderRead)
def mark_order_paid_in_sandbox(
    order_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = (
        db.query(Order)
        .filter(Order.id == order_id, Order.user_id == current_user.id)
        .with_for_update()
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    payment = _get_order_payment(db, order.id)
    if not payment:
        raise HTTPException(status_code=500, detail="Payment was not created for this order")

    if order.status != "awaiting_payment":
        raise HTTPException(status_code=400, detail="Only awaiting_payment order can be paid")

    now = _now()
    order.status = "paid"
    order.paid_at = now
    order.updated_at = now
    payment.status = "paid"
    payment.paid_at = now
    payment.updated_at = now

    order_items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
    for order_item in order_items:
        order_item.status = "paid"
        order_item.updated_at = now
        db.add(order_item)

    _add_transaction(db, payment, tx_type="sandbox_payment_succeeded", tx_status="success")
    db.add(order)
    db.add(payment)
    db.commit()
    db.refresh(order)
    return _order_to_read(db, order)
