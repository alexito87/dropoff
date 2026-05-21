from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user, get_db
from app.core.admin import is_admin, require_admin
from app.events.cart_events import (
    add_cart_checkout_requested_event_to_outbox,
    add_cart_cleared_event_to_outbox,
    add_cart_item_added_event_to_outbox,
    add_cart_item_removed_event_to_outbox,
)
from app.models.item_image import ItemImage
from app.models.rental import Rental
from app.modules.items.models.item import Item
from app.modules.orders.models.cart import Cart, CartItem
from app.modules.orders.models.order import Order
from app.modules.orders.schemas.cart import (
    CartItemCreate,
    CartItemRead,
    CartRead,
)
from app.modules.orders.schemas.order import OrderCreate
from app.modules.payments.models.payment import Payment, StripeCheckoutSession
from app.modules.users.models.user import User

router = APIRouter()

DELIVERY_METHODS = {
    "pickup": 0,
    "courier_standard": 1200,
}

SUPPORTED_PAYMENT_METHODS = {"stripe_checkout"}


def _now():
    return datetime.now(timezone.utc)


def _days_count(start_date, end_date) -> int:
    return (end_date - start_date).days + 1


def _get_user_or_404(db: Session, user_id: UUID) -> User:
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user


def _get_cart_or_404(db: Session, cart_id: UUID) -> Cart:
    cart = db.query(Cart).filter(Cart.id == cart_id).first()

    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")

    return cart


def _get_or_create_active_cart(db: Session, user_id: UUID) -> Cart:
    cart = (
        db.query(Cart)
        .filter(Cart.user_id == user_id, Cart.status == "active")
        .options(joinedload(Cart.items))
        .first()
    )

    if cart:
        return cart

    cart = Cart(user_id=user_id, status="active")
    db.add(cart)
    db.flush()

    return cart


def _get_active_cart_for_user(db: Session, user_id: UUID) -> Cart | None:
    return (
        db.query(Cart)
        .filter(Cart.user_id == user_id, Cart.status == "active")
        .first()
    )


def _first_image_url(db: Session, item_id: UUID) -> str | None:
    image = (
        db.query(ItemImage)
        .filter(ItemImage.item_id == item_id)
        .order_by(ItemImage.sort_order.asc(), ItemImage.created_at.asc())
        .first()
    )

    return image.url if image else None


def _has_unavailable_overlap(db: Session, item_id: UUID, start_date, end_date) -> bool:
    return db.query(
        db.query(Rental)
        .filter(
            Rental.item_id == item_id,
            Rental.status == "approved",
            Rental.start_date <= end_date,
            Rental.end_date >= start_date,
        )
        .exists()
    ).scalar()


def _cart_item_to_read(db: Session, cart_item: CartItem) -> CartItemRead:
    item = db.query(Item).filter(Item.id == cart_item.item_id).first()
    owner = db.query(User).filter(User.id == item.owner_id).first() if item else None
    days_count = _days_count(cart_item.rent_start, cart_item.rent_end)
    line_total_cents = cart_item.rent_total_cents + cart_item.total_deposit_cents

    return CartItemRead(
        id=cart_item.id,
        item_id=cart_item.item_id,
        item_title=item.title if item else "",
        owner_id=item.owner_id if item else UUID("00000000-0000-0000-0000-000000000000"),
        owner_name=owner.full_name if owner else None,
        image_url=_first_image_url(db, cart_item.item_id),
        rent_start=cart_item.rent_start,
        rent_end=cart_item.rent_end,
        days_count=days_count,
        quantity=cart_item.quantity,
        daily_price_cents=cart_item.daily_price_cents,
        deposit_cents=cart_item.deposit_cents,
        rent_total_cents=cart_item.rent_total_cents,
        total_deposit_cents=cart_item.total_deposit_cents,
        line_total_cents=line_total_cents,
        created_at=cart_item.created_at,
    )


def _cart_to_read(db: Session, cart: Cart | None) -> CartRead:
    if not cart:
        return CartRead()

    cart_items = (
        db.query(CartItem)
        .filter(CartItem.cart_id == cart.id)
        .order_by(CartItem.created_at.asc())
        .all()
    )

    items = [_cart_item_to_read(db, cart_item) for cart_item in cart_items]
    items_total = sum(item.rent_total_cents for item in items)
    deposit_total = sum(item.total_deposit_cents for item in items)

    return CartRead(
        id=cart.id,
        status=cart.status,
        items=items,
        items_total_cents=items_total,
        deposit_total_cents=deposit_total,
        payable_total_cents=items_total + deposit_total,
        items_count=sum(item.quantity for item in items),
    )


def _assert_cart_access(cart: Cart, current_user: User) -> None:
    if is_admin(current_user):
        return

    if cart.user_id == current_user.id:
        return

    raise HTTPException(status_code=403, detail="Access denied")


def _add_item_to_cart_for_user(
    *,
    db: Session,
    payload: CartItemCreate,
    target_user: User,
    actor_user: User,
) -> Cart:
    item = db.query(Item).filter(Item.id == payload.item_id, Item.status == "published").first()

    if not item:
        raise HTTPException(status_code=404, detail="Published item not found")

    if item.owner_id == target_user.id and not is_admin(actor_user):
        raise HTTPException(status_code=400, detail="You cannot add your own item to cart")

    if payload.rent_end < payload.rent_start:
        raise HTTPException(status_code=400, detail="End date cannot be earlier than start date")

    if _has_unavailable_overlap(db, item.id, payload.rent_start, payload.rent_end):
        raise HTTPException(status_code=400, detail="Item is unavailable for selected dates")

    cart = _get_or_create_active_cart(db, target_user.id)
    days_count = _days_count(payload.rent_start, payload.rent_end)
    rent_total_cents = item.daily_price_cents * days_count * payload.quantity
    total_deposit_cents = item.deposit_cents * payload.quantity

    existing = (
        db.query(CartItem)
        .filter(
            CartItem.cart_id == cart.id,
            CartItem.item_id == item.id,
            CartItem.rent_start == payload.rent_start,
            CartItem.rent_end == payload.rent_end,
        )
        .first()
    )

    if existing:
        existing.quantity = payload.quantity
        existing.daily_price_cents = item.daily_price_cents
        existing.deposit_cents = item.deposit_cents
        existing.rent_total_cents = rent_total_cents
        existing.total_deposit_cents = total_deposit_cents
        existing.updated_at = _now()
        cart_item = existing
        db.add(cart_item)
    else:
        cart_item = CartItem(
            cart_id=cart.id,
            item_id=item.id,
            rent_start=payload.rent_start,
            rent_end=payload.rent_end,
            quantity=payload.quantity,
            daily_price_cents=item.daily_price_cents,
            deposit_cents=item.deposit_cents,
            rent_total_cents=rent_total_cents,
            total_deposit_cents=total_deposit_cents,
        )
        db.add(cart_item)

    cart.updated_at = _now()
    db.add(cart)
    db.flush()

    add_cart_item_added_event_to_outbox(
        db,
        cart=cart,
        cart_item=cart_item,
        user_id=target_user.id,
    )

    return cart


def _remove_cart_item_from_cart(
    *,
    db: Session,
    cart: Cart,
    cart_item: CartItem,
) -> Cart:
    add_cart_item_removed_event_to_outbox(
        db,
        cart=cart,
        cart_item=cart_item,
        user_id=cart.user_id,
    )

    db.delete(cart_item)
    cart.updated_at = _now()
    db.add(cart)

    return cart


def _clear_cart_items(
    *,
    db: Session,
    cart: Cart,
) -> Cart:
    items_count = db.query(CartItem).filter(CartItem.cart_id == cart.id).count()

    add_cart_cleared_event_to_outbox(
        db,
        cart=cart,
        user_id=cart.user_id,
        items_count=items_count,
    )

    db.query(CartItem).filter(CartItem.cart_id == cart.id).delete()
    cart.updated_at = _now()
    db.add(cart)

    return cart


@router.get("", response_model=CartRead)
def read_active_cart(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cart = _get_active_cart_for_user(db, current_user.id)

    return _cart_to_read(db, cart)


@router.post("/items", response_model=CartRead, status_code=status.HTTP_201_CREATED)
def add_item_to_cart(
    payload: CartItemCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cart = _add_item_to_cart_for_user(
        db=db,
        payload=payload,
        target_user=current_user,
        actor_user=current_user,
    )

    db.commit()
    db.refresh(cart)

    return _cart_to_read(db, cart)


@router.post("/checkout-request", status_code=status.HTTP_202_ACCEPTED)
def request_cart_checkout(
    payload: OrderCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.delivery_method not in DELIVERY_METHODS:
        raise HTTPException(status_code=400, detail="Unsupported delivery method")

    if payload.payment_method not in SUPPORTED_PAYMENT_METHODS:
        raise HTTPException(
            status_code=400,
            detail="For MVP only stripe_checkout is supported",
        )

    cart = (
        db.query(Cart)
        .filter(Cart.user_id == current_user.id, Cart.status == "active")
        .with_for_update()
        .first()
    )

    if not cart:
        raise HTTPException(status_code=400, detail="Active cart is empty")

    cart_items_count = db.query(CartItem).filter(CartItem.cart_id == cart.id).count()

    if cart_items_count == 0:
        raise HTTPException(status_code=400, detail="Active cart is empty")

    add_cart_checkout_requested_event_to_outbox(
        db,
        cart=cart,
        user_id=current_user.id,
        delivery_method=payload.delivery_method,
        payment_method=payload.payment_method,
    )

    db.commit()

    return {
        "accepted": True,
        "event_type": "cart.checkout_requested",
        "cart_id": str(cart.id),
        "cart_status": cart.status,
        "message": "Checkout request accepted. Order will be created by event consumer.",
    }


@router.get("/checkout-status")
def read_cart_checkout_status(
    cart_id: UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cart = _get_cart_or_404(db, cart_id)

    _assert_cart_access(cart, current_user)

    order = (
        db.query(Order)
        .filter(Order.cart_id == cart.id)
        .order_by(Order.created_at.desc())
        .first()
    )

    if not order:
        return {
            "status": "processing",
            "cart_id": str(cart.id),
            "cart_status": cart.status,
            "order_id": None,
            "order_status": None,
            "payment_id": None,
            "payment_status": None,
            "stripe_checkout_session_id": None,
            "checkout_url": None,
            "message": "Checkout request is still being processed.",
        }

    payment = (
        db.query(Payment)
        .filter(Payment.order_id == order.id)
        .order_by(Payment.created_at.desc())
        .first()
    )

    checkout_session = None

    if payment:
        checkout_session = (
            db.query(StripeCheckoutSession)
            .filter(StripeCheckoutSession.payment_id == payment.id)
            .order_by(StripeCheckoutSession.created_at.desc())
            .first()
        )

    checkout_url = checkout_session.checkout_url if checkout_session else None
    stripe_checkout_session_id = (
        checkout_session.provider_session_id
        if checkout_session
        else order.stripe_checkout_session_id
    )

    if checkout_url:
        status_value = "checkout_ready"
        message = "Checkout session is ready."
    elif payment and payment.status in {"failed", "expired", "cancelled"}:
        status_value = "payment_failed"
        message = f"Payment is {payment.status}."
    elif checkout_session and checkout_session.status == "failed":
        status_value = "checkout_failed"
        message = "Checkout session creation failed."
    else:
        status_value = "order_created"
        message = "Order was created, checkout session is not ready yet."

    return {
        "status": status_value,
        "cart_id": str(cart.id),
        "cart_status": cart.status,
        "order_id": str(order.id),
        "order_status": order.status,
        "payment_id": str(payment.id) if payment else None,
        "payment_status": payment.status if payment else None,
        "stripe_checkout_session_id": stripe_checkout_session_id,
        "checkout_url": checkout_url,
        "message": message,
    }


@router.delete("/items/{cart_item_id}", response_model=CartRead)
def remove_cart_item(
    cart_item_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cart_item = db.query(CartItem).filter(CartItem.id == cart_item_id).first()

    if not cart_item:
        raise HTTPException(status_code=404, detail="Cart item not found")

    cart = _get_cart_or_404(db, cart_item.cart_id)

    _assert_cart_access(cart, current_user)

    _remove_cart_item_from_cart(
        db=db,
        cart=cart,
        cart_item=cart_item,
    )

    db.commit()
    db.refresh(cart)

    return _cart_to_read(db, cart)


@router.delete("", response_model=CartRead)
def clear_cart(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cart = _get_active_cart_for_user(db, current_user.id)

    if not cart:
        return CartRead()

    _clear_cart_items(db=db, cart=cart)

    db.commit()
    db.refresh(cart)

    return _cart_to_read(db, cart)


@router.get("/admin", response_model=list[CartRead])
def read_all_active_carts_as_admin(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    carts = (
        db.query(Cart)
        .filter(Cart.status == "active")
        .order_by(Cart.updated_at.desc())
        .limit(200)
        .all()
    )

    return [_cart_to_read(db, cart) for cart in carts]


@router.get("/admin/users/{user_id}", response_model=CartRead)
def read_user_active_cart_as_admin(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    _get_user_or_404(db, user_id)

    cart = _get_active_cart_for_user(db, user_id)

    return _cart_to_read(db, cart)


@router.post("/admin/users/{user_id}/items", response_model=CartRead, status_code=status.HTTP_201_CREATED)
def add_item_to_user_cart_as_admin(
    user_id: UUID,
    payload: CartItemCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    target_user = _get_user_or_404(db, user_id)

    cart = _add_item_to_cart_for_user(
        db=db,
        payload=payload,
        target_user=target_user,
        actor_user=current_user,
    )

    db.commit()
    db.refresh(cart)

    return _cart_to_read(db, cart)


@router.get("/admin/{cart_id}", response_model=CartRead)
def read_cart_as_admin(
    cart_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    cart = _get_cart_or_404(db, cart_id)

    return _cart_to_read(db, cart)


@router.delete("/admin/{cart_id}", response_model=CartRead)
def clear_cart_as_admin(
    cart_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    cart = _get_cart_or_404(db, cart_id)

    _clear_cart_items(db=db, cart=cart)

    db.commit()
    db.refresh(cart)

    return _cart_to_read(db, cart)