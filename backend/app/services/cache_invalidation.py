import logging
from uuid import UUID

from app.services.cache import cache_service
from app.services.cache_keys import catalog_item_details_key, catalog_search_namespace

logger = logging.getLogger(__name__)


def invalidate_catalog_item(item_id: UUID) -> None:
    deleted_count = cache_service.delete(catalog_item_details_key(str(item_id)))
    logger.info(
        "Catalog item details cache invalidated for item_id=%s, deleted=%s",
        item_id,
        deleted_count,
    )


def bump_catalog_search_namespace() -> int:
    new_version = cache_service.bump_namespace_version(catalog_search_namespace())
    logger.info("Catalog search namespace bumped to v%s", new_version)
    return new_version


def invalidate_public_catalog_for_item(item_id: UUID) -> None:
    invalidate_catalog_item(item_id)
    bump_catalog_search_namespace()


def invalidate_public_catalog_if_published(item_id: UUID, item_status: str) -> None:
    if item_status != "published":
        logger.info(
            "Skipping public catalog cache invalidation for item_id=%s because status=%s",
            item_id,
            item_status,
        )
        return

    invalidate_public_catalog_for_item(item_id)