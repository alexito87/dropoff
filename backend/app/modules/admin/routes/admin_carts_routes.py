from datetime import date
from math import ceil
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, get_db
from app.core.admin import require_admin
from app.modules.admin.schemas.admin_carts import (
    AdminCartDetailsRead,
    AdminCartItemRead,
    AdminCartRead,
    AdminCartsResponse,
    AdminCartUserRead,
)
from app.modules.items.models.item import Item
from app.modules.orders.models.cart import Cart, CartItem
from app.modules.users.models.user import User

router = APIRouter()


CART_STATUSES = {
    "active",
    "converted",
    "abandoned",
    "cancelled",
}


def _get_cart_or_404(db: Session, cart_id: UUID) -> Cart:
    cart = (
        db.query(Cart)
        .options(
            selectinload(Cart.items),
            selectinload(Cart.user),
        )
        .filter(Cart.id == cart_id)
        .first()
    )

    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")

    return cart


def _get_user_or_none(db: Session, user_id: UUID) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def _get_item_or_none(db: Session, item_id: UUID) -> Item | None:
    return db.query(Item).filter(Item.id == item_id).first()


def _serialize_user(user: User | None) -> AdminCartUserRead | None:
    if not user:
        return None

    return AdminCartUserRead(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        email_verified=user.email_verified,
    )


def _serialize_cart_item(db: Session, cart_item: CartItem) -> AdminCartItemRead:
    item = _get_item_or_none(db, cart_item.item_id)
    owner = _get_user_or_none(db, item.owner_id) if item else None

    return AdminCartItemRead(
        id=cart_item.id,
        cart_id=cart_item.cart_id,
        item_id=cart_item.item_id,
        item_title=item.title if item else None,
        item_status=item.status if item else None,
        owner_id=item.owner_id if item else None,
        owner_email=owner.email if owner else None,
        rent_start=cart_item.rent_start,
        rent_end=cart_item.rent_end,
        quantity=cart_item.quantity,
        daily_price_cents=cart_item.daily_price_cents,
        deposit_cents=cart_item.deposit_cents,
        rent_total_cents=cart_item.rent_total_cents,
        total_deposit_cents=cart_item.total_deposit_cents,
        line_total_cents=cart_item.rent_total_cents + cart_item.total_deposit_cents,
        created_at=cart_item.created_at,
        updated_at=cart_item.updated_at,
    )


def _cart_items(db: Session, cart_id: UUID) -> list[CartItem]:
    return (
        db.query(CartItem)
        .filter(CartItem.cart_id == cart_id)
        .order_by(CartItem.created_at.asc())
        .all()
    )


def _cart_totals(cart_items: list[CartItem]) -> dict:
    items_total_cents = sum(item.rent_total_cents for item in cart_items)
    deposit_total_cents = sum(item.total_deposit_cents for item in cart_items)

    return {
        "items_count": sum(item.quantity for item in cart_items),
        "items_total_cents": items_total_cents,
        "deposit_total_cents": deposit_total_cents,
        "payable_total_cents": items_total_cents + deposit_total_cents,
    }


def _serialize_cart(db: Session, cart: Cart) -> AdminCartRead:
    user = cart.user if getattr(cart, "user", None) else _get_user_or_none(db, cart.user_id)
    cart_items = _cart_items(db, cart.id)
    totals = _cart_totals(cart_items)

    return AdminCartRead(
        id=cart.id,
        user_id=cart.user_id,
        status=cart.status,
        user=_serialize_user(user),
        items_count=totals["items_count"],
        items_total_cents=totals["items_total_cents"],
        deposit_total_cents=totals["deposit_total_cents"],
        payable_total_cents=totals["payable_total_cents"],
        created_at=cart.created_at,
        updated_at=cart.updated_at,
    )


def _serialize_cart_details(db: Session, cart: Cart) -> AdminCartDetailsRead:
    user = cart.user if getattr(cart, "user", None) else _get_user_or_none(db, cart.user_id)
    cart_items = _cart_items(db, cart.id)
    totals = _cart_totals(cart_items)

    return AdminCartDetailsRead(
        id=cart.id,
        user_id=cart.user_id,
        status=cart.status,
        user=_serialize_user(user),
        items_count=totals["items_count"],
        items_total_cents=totals["items_total_cents"],
        deposit_total_cents=totals["deposit_total_cents"],
        payable_total_cents=totals["payable_total_cents"],
        created_at=cart.created_at,
        updated_at=cart.updated_at,
        items=[_serialize_cart_item(db, item) for item in cart_items],
    )


@router.get("", response_model=AdminCartsResponse)
def read_carts_as_admin(
    status: str | None = Query(default=None),
    user_id: UUID | None = Query(default=None),
    created_from: date | None = Query(default=None),
    created_to: date | None = Query(default=None),
    updated_from: date | None = Query(default=None),
    updated_to: date | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    if status and status not in CART_STATUSES:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Unsupported cart status",
                "allowed_statuses": sorted(CART_STATUSES),
            },
        )

    base_query = db.query(Cart).options(selectinload(Cart.user))

    if status:
        base_query = base_query.filter(Cart.status == status)

    if user_id:
        base_query = base_query.filter(Cart.user_id == user_id)

    if created_from:
        base_query = base_query.filter(Cart.created_at >= created_from)

    if created_to:
        base_query = base_query.filter(Cart.created_at < created_to)

    if updated_from:
        base_query = base_query.filter(Cart.updated_at >= updated_from)

    if updated_to:
        base_query = base_query.filter(Cart.updated_at < updated_to)

    total = base_query.count()
    pages = ceil(total / page_size) if total > 0 else 1
    offset = (page - 1) * page_size

    carts = (
        base_query
        .order_by(Cart.updated_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    return AdminCartsResponse(
        carts=[_serialize_cart(db, cart) for cart in carts],
        page=page,
        page_size=page_size,
        total=total,
        pages=pages,
    )


@router.get("/converted", response_model=AdminCartsResponse)
def read_converted_carts_as_admin(
    user_id: UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    base_query = (
        db.query(Cart)
        .options(selectinload(Cart.user))
        .filter(Cart.status == "converted")
    )

    if user_id:
        base_query = base_query.filter(Cart.user_id == user_id)

    total = base_query.count()
    pages = ceil(total / page_size) if total > 0 else 1
    offset = (page - 1) * page_size

    carts = (
        base_query
        .order_by(Cart.updated_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    return AdminCartsResponse(
        carts=[_serialize_cart(db, cart) for cart in carts],
        page=page,
        page_size=page_size,
        total=total,
        pages=pages,
    )


@router.get("/users/{user_id}", response_model=AdminCartsResponse)
def read_user_carts_as_admin(
    user_id: UUID,
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    user = _get_user_or_none(db, user_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if status and status not in CART_STATUSES:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Unsupported cart status",
                "allowed_statuses": sorted(CART_STATUSES),
            },
        )

    base_query = (
        db.query(Cart)
        .options(selectinload(Cart.user))
        .filter(Cart.user_id == user_id)
    )

    if status:
        base_query = base_query.filter(Cart.status == status)

    total = base_query.count()
    pages = ceil(total / page_size) if total > 0 else 1
    offset = (page - 1) * page_size

    carts = (
        base_query
        .order_by(Cart.updated_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    return AdminCartsResponse(
        carts=[_serialize_cart(db, cart) for cart in carts],
        page=page,
        page_size=page_size,
        total=total,
        pages=pages,
    )


@router.get("/{cart_id}", response_model=AdminCartDetailsRead)
def read_cart_details_as_admin(
    cart_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    cart = _get_cart_or_404(db, cart_id)

    return _serialize_cart_details(db, cart)