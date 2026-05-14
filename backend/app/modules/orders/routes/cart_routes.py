from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user, get_db
from app.models.cart import Cart, CartItem
from app.models.item import Item
from app.models.item_image import ItemImage
from app.models.rental import Rental
from app.models.user import User
from app.schemas.cart import CartItemCreate, CartRead, CartItemRead

router = APIRouter()


def _days_count(start_date, end_date) -> int:
    return (end_date - start_date).days + 1


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


@router.get("", response_model=CartRead)
def read_active_cart(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cart = db.query(Cart).filter(Cart.user_id == current_user.id, Cart.status == "active").first()
    return _cart_to_read(db, cart)


@router.post("/items", response_model=CartRead, status_code=status.HTTP_201_CREATED)
def add_item_to_cart(
    payload: CartItemCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = db.query(Item).filter(Item.id == payload.item_id, Item.status == "published").first()
    if not item:
        raise HTTPException(status_code=404, detail="Published item not found")

    if item.owner_id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot add your own item to cart")

    if payload.rent_end < payload.rent_start:
        raise HTTPException(status_code=400, detail="End date cannot be earlier than start date")

    if _has_unavailable_overlap(db, item.id, payload.rent_start, payload.rent_end):
        raise HTTPException(status_code=400, detail="Item is unavailable for selected dates")

    cart = _get_or_create_active_cart(db, current_user.id)
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
        existing.daily_price_cents = item.daily_price_cents
        existing.deposit_cents = item.deposit_cents
        existing.rent_total_cents = rent_total_cents
        existing.total_deposit_cents = total_deposit_cents
        existing.updated_at = datetime.now(timezone.utc)
        db.add(existing)
    else:
        db.add(
            CartItem(
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
        )

    cart.updated_at = datetime.now(timezone.utc)
    db.add(cart)
    db.commit()
    db.refresh(cart)
    return _cart_to_read(db, cart)


@router.delete("/items/{cart_item_id}", response_model=CartRead)
def remove_cart_item(
    cart_item_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cart = db.query(Cart).filter(Cart.user_id == current_user.id, Cart.status == "active").first()
    if not cart:
        return CartRead()

    cart_item = db.query(CartItem).filter(CartItem.id == cart_item_id, CartItem.cart_id == cart.id).first()
    if not cart_item:
        raise HTTPException(status_code=404, detail="Cart item not found")

    db.delete(cart_item)
    cart.updated_at = datetime.now(timezone.utc)
    db.add(cart)
    db.commit()
    return _cart_to_read(db, cart)


@router.delete("", response_model=CartRead)
def clear_cart(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cart = db.query(Cart).filter(Cart.user_id == current_user.id, Cart.status == "active").first()
    if not cart:
        return CartRead()

    db.query(CartItem).filter(CartItem.cart_id == cart.id).delete()
    cart.updated_at = datetime.now(timezone.utc)
    db.add(cart)
    db.commit()
    db.refresh(cart)
    return _cart_to_read(db, cart)
