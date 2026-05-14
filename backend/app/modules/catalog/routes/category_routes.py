from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings
from app.models.category import Category
from app.schemas.category import CategoryRead
from app.services.cache import cache_service
from app.services.cache_keys import categories_key
from app.services.etag import build_etag

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("", response_model=list[CategoryRead])
def read_categories(
    response: Response,
    db: Session = Depends(get_db),
    if_none_match: str | None = Header(default=None),
) -> list[CategoryRead] | Response:
    cache_key = categories_key()

    cached_payload = cache_service.get_json(cache_key)
    if cached_payload is not None:
        logger.info("Categories cache hit")
        response_payload = cached_payload
    else:
        logger.info("Categories cache miss")

        categories = db.query(Category).order_by(Category.name.asc()).all()
        response_payload = [
            CategoryRead.model_validate(category).model_dump(mode="json")
            for category in categories
        ]

        cache_service.set_json(
            key=cache_key,
            value=response_payload,
            ttl_seconds=settings.CACHE_TTL_CATEGORIES_SECONDS,
        )

    etag = build_etag(response_payload)

    if if_none_match == etag:
        logger.info("Categories ETag match -> 304")
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers={"ETag": etag})

    response.headers["ETag"] = etag
    return [CategoryRead.model_validate(item) for item in response_payload]