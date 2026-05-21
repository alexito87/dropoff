from fastapi import HTTPException


def is_admin(user) -> bool:
    return bool(getattr(user, "is_superuser", False))


def require_admin(user) -> None:
    if not is_admin(user):
        raise HTTPException(status_code=403, detail="Only admin can perform this action")
