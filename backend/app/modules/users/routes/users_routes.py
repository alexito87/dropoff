from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.admin import is_admin, require_admin
from app.modules.users.models.user import User
from app.modules.users.schemas.user import UserRead, UserUpdate

router = APIRouter()


def _get_user_or_404(db: Session, user_id: UUID) -> User:
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user


def _apply_user_update(user: User, payload: UserUpdate) -> None:
    user.full_name = payload.full_name
    user.phone = payload.phone
    user.city = payload.city


@router.get("/me", response_model=UserRead)
def read_me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.patch("/me", response_model=UserRead)
def update_me(
    payload: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    _apply_user_update(current_user, payload)

    db.add(current_user)
    db.commit()
    db.refresh(current_user)

    return current_user


@router.get("/admin", response_model=list[UserRead])
def read_all_users_as_admin(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    users = (
        db.query(User)
        .order_by(User.created_at.desc())
        .limit(500)
        .all()
    )

    return users


@router.get("/{user_id}", response_model=UserRead)
def read_user(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not is_admin(current_user) and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    return _get_user_or_404(db, user_id)


@router.patch("/{user_id}", response_model=UserRead)
def update_user_as_admin(
    user_id: UUID,
    payload: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    user = _get_user_or_404(db, user_id)

    _apply_user_update(user, payload)

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


@router.post("/{user_id}/activate", response_model=UserRead)
def activate_user_as_admin(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    user = _get_user_or_404(db, user_id)

    if hasattr(user, "is_active"):
        user.is_active = True
    else:
        raise HTTPException(
            status_code=400,
            detail="User model does not support is_active field",
        )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


@router.post("/{user_id}/deactivate", response_model=UserRead)
def deactivate_user_as_admin(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    user = _get_user_or_404(db, user_id)

    if user.id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="Admin cannot deactivate own account",
        )

    if hasattr(user, "is_active"):
        user.is_active = False
    else:
        raise HTTPException(
            status_code=400,
            detail="User model does not support is_active field",
        )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user