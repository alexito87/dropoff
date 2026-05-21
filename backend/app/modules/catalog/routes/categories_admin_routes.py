from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.admin import require_admin
from app.modules.catalog.models.category import Category
from app.modules.catalog.schemas.category import CategoryRead
from app.modules.catalog.schemas.category_admin import CategoryCreate, CategoryUpdate
from app.modules.items.models.item import Item
from app.modules.users.models.user import User

router = APIRouter()


def _normalize_category_name(name: str) -> str:
    return name.strip()


def _get_category_or_404(db: Session, category_id: UUID) -> Category:
    category = db.query(Category).filter(Category.id == category_id).first()

    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    return category


def _ensure_category_name_unique(
    db: Session,
    *,
    name: str,
    exclude_category_id: UUID | None = None,
) -> None:
    query = db.query(Category).filter(func.lower(Category.name) == name.lower())

    if exclude_category_id is not None:
        query = query.filter(Category.id != exclude_category_id)

    existing = query.first()

    if existing:
        raise HTTPException(status_code=400, detail="Category with this name already exists")


@router.get("/admin/categories", response_model=list[CategoryRead])
def read_all_categories_as_admin(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    categories = (
        db.query(Category)
        .order_by(Category.name.asc())
        .all()
    )

    return categories


@router.post(
    "/admin/categories",
    response_model=CategoryRead,
    status_code=status.HTTP_201_CREATED,
)
def create_category_as_admin(
    payload: CategoryCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    name = _normalize_category_name(payload.name)

    if not name:
        raise HTTPException(status_code=400, detail="Category name cannot be empty")

    _ensure_category_name_unique(db, name=name)

    category = Category(name=name)

    db.add(category)
    db.commit()
    db.refresh(category)

    return category


@router.patch("/admin/categories/{category_id}", response_model=CategoryRead)
def update_category_as_admin(
    category_id: UUID,
    payload: CategoryUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    category = _get_category_or_404(db, category_id)
    name = _normalize_category_name(payload.name)

    if not name:
        raise HTTPException(status_code=400, detail="Category name cannot be empty")

    _ensure_category_name_unique(
        db,
        name=name,
        exclude_category_id=category.id,
    )

    category.name = name

    db.add(category)
    db.commit()
    db.refresh(category)

    return category


@router.delete("/admin/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category_as_admin(
    category_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    category = _get_category_or_404(db, category_id)

    linked_items_count = (
        db.query(func.count(Item.id))
        .filter(Item.category_id == category.id)
        .scalar()
        or 0
    )

    if linked_items_count > 0:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete category because it has linked items",
        )

    db.delete(category)
    db.commit()

    return None