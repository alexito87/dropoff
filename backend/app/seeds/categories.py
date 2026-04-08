
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.models.category import Category

DEFAULT_CATEGORIES = [
    "Инструменты",
    "Спорт и туризм",
    "Электроника",
    "Фото и видео",
    "Бытовая техника",
    "Для детей",
    "Одежда и аксессуары",
    "Сад и дача",
    "Музыкальные инструменты",
    "Другое",
]


def seed_categories(db: Session) -> None:
    existing_names = {name for (name,) in db.query(Category.name).all()}
    missing = [Category(name=name) for name in DEFAULT_CATEGORIES if name not in existing_names]
    if missing:
        db.add_all(missing)
        db.commit()


if __name__ == "__main__":
    db = SessionLocal()
    try:
        seed_categories(db)
        print("Categories seeded")
    finally:
        db.close()
