import json
from uuid import UUID


def categories_key() -> str:
    return "categories:all"


def catalog_item_details_key(item_id: str) -> str:
    return f"catalog:item:{item_id}:details"


def catalog_search_namespace() -> str:
    return "catalog_search"


def catalog_search_key(
    *,
    namespace_version: int,
    city: str | None,
    category_id: UUID | None,
    price_from: int | None,
    price_to: int | None,
    page: int,
    page_size: int,
    sort: str,
) -> str:
    normalized_payload = {
        "city": city.strip().lower() if city else None,
        "category_id": str(category_id) if category_id else None,
        "price_from": price_from,
        "price_to": price_to,
        "page": page,
        "page_size": page_size,
        "sort": sort,
    }
    payload_json = json.dumps(normalized_payload, sort_keys=True, separators=(",", ":"))
    return f"catalog:v{namespace_version}:search:{payload_json}"