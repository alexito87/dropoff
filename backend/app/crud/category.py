from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.category import Category


def get_categories(db: Session) -> list[Category]:
    statement = select(Category).order_by(Category.name.asc())
    return list(db.scalars(statement).all())
