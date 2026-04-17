import logging
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.models.item import Item
from app.models.item_image import ItemImage
from app.models.user import User
from app.schemas.item import ItemCreate, ItemRead, ItemUpdate
from app.schemas.item_image import ItemImageRead
from app.services.cache_invalidation import invalidate_public_catalog_if_published
from app.services.image_url import build_versioned_image_url
from app.services.supabase_storage_service import SupabaseStorageService

router = APIRouter()
logger = logging.getLogger(__name__)


def _serialize_item_image(image: ItemImage) -> ItemImageRead:
    return ItemImageRead(
        id=image.id,
        item_id=image.item_id,
        url=image.url,
        versioned_url=build_versioned_image_url(image.url, image.version),
        storage_path=image.storage_path,
        mime_type=image.mime_type,
        file_size_bytes=image.file_size_bytes,
        sort_order=image.sort_order,
        version=image.version,
        created_at=image.created_at,
    )


def _serialize_item(item: Item) -> ItemRead:
    return ItemRead(
        id=item.id,
        owner_id=item.owner_id,
        category_id=item.category_id,
        title=item.title,
        description=item.description,
        daily_price_cents=item.daily_price_cents,
        deposit_cents=item.deposit_cents,
        city=item.city,
        pickup_address=item.pickup_address,
        status=item.status,
        moderated_by=item.moderated_by,
        moderated_at=item.moderated_at,
        moderation_comment=item.moderation_comment,
        created_at=item.created_at,
        updated_at=item.updated_at,
        images=[_serialize_item_image(image) for image in item.images],
    )


def _get_owned_item(db: Session, item_id: UUID, owner_id: UUID) -> Item:
    item = (
        db.query(Item)
        .options(selectinload(Item.images))
        .filter(Item.id == item_id, Item.owner_id == owner_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


def _ensure_item_editable(item: Item):
    if item.status not in {"draft", "rejected"}:
        raise HTTPException(
            status_code=400,
            detail="Only draft or rejected item can be changed",
        )


def _ensure_image_replace_allowed(item: Item):
    if item.status not in {"draft", "rejected", "published"}:
        raise HTTPException(
            status_code=400,
            detail="Image replace is allowed only for draft, rejected, or published item",
        )


def _validate_image_upload(file: UploadFile, file_bytes: bytes) -> tuple[str, str]:
    mime_type = (file.content_type or "").lower()
    if mime_type not in settings.allowed_item_image_mime_types:
        raise HTTPException(status_code=400, detail="Unsupported image type. Allowed: JPEG, PNG, WebP")

    if not file_bytes:
        raise HTTPException(status_code=400, detail="Empty or corrupted file")
    if len(file_bytes) > settings.MAX_ITEM_IMAGE_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="File is too large. Maximum size is 5 MB")

    ext = Path(file.filename or "image").suffix.lower().replace(".", "")
    if ext not in {"jpg", "jpeg", "png", "webp"}:
        raise HTTPException(status_code=400, detail="Unsupported file extension")

    return mime_type, ext


@router.get("/my", response_model=list[ItemRead])
def read_my_items(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = (
        db.query(Item)
        .options(selectinload(Item.images))
        .filter(Item.owner_id == current_user.id)
        .order_by(Item.created_at.desc())
        .all()
    )
    return [_serialize_item(item) for item in items]


@router.post("", response_model=ItemRead, status_code=status.HTTP_201_CREATED)
def create_item(payload: ItemCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = Item(owner_id=current_user.id, status="draft", **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize_item(item)


@router.get("/{item_id}", response_model=ItemRead)
def read_item(item_id: UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _serialize_item(_get_owned_item(db, item_id, current_user.id))


@router.patch("/{item_id}", response_model=ItemRead)
def update_item(item_id: UUID, payload: ItemUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = _get_owned_item(db, item_id, current_user.id)
    old_status = item.status
    _ensure_item_editable(item)

    for field, value in payload.model_dump().items():
        setattr(item, field, value)

    db.add(item)
    db.commit()
    invalidate_public_catalog_if_published(item.id, old_status)
    db.refresh(item)
    return _serialize_item(item)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(item_id: UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = _get_owned_item(db, item_id, current_user.id)
    old_status = item.status
    _ensure_item_editable(item)

    storage = SupabaseStorageService()
    for image in item.images:
        try:
            storage.remove_file(image.storage_path)
        except Exception:
            pass

    db.delete(item)
    db.commit()
    invalidate_public_catalog_if_published(item.id, old_status)
    return None


@router.post("/{item_id}/submit-for-moderation", response_model=ItemRead)
def submit_item_for_moderation(
    item_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = _get_owned_item(db, item_id, current_user.id)

    if item.status not in {"draft", "rejected"}:
        raise HTTPException(status_code=400, detail="Only draft or rejected item can be submitted")

    if not item.images:
        raise HTTPException(status_code=400, detail="At least one image is required")

    item.status = "pending_review"
    item.moderated_by = None
    item.moderated_at = None
    item.moderation_comment = None

    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize_item(item)


@router.post("/{item_id}/images", response_model=ItemImageRead, status_code=status.HTTP_201_CREATED)
async def upload_item_image(
    item_id: UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = _get_owned_item(db, item_id, current_user.id)
    current_status = item.status
    _ensure_item_editable(item)

    existing_count = db.query(func.count(ItemImage.id)).filter(ItemImage.item_id == item.id).scalar() or 0
    if existing_count >= settings.MAX_ITEM_IMAGE_COUNT:
        raise HTTPException(status_code=400, detail=f"Maximum {settings.MAX_ITEM_IMAGE_COUNT} images per item")

    file_bytes = await file.read()
    mime_type, ext = _validate_image_upload(file, file_bytes)

    storage = SupabaseStorageService()
    try:
        uploaded = storage.upload_bytes(str(item.id), file_bytes=file_bytes, extension=ext, mime_type=mime_type)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to upload image to storage: {exc}") from exc

    image = ItemImage(
        item_id=item.id,
        url=uploaded.public_url,
        storage_path=uploaded.storage_path,
        mime_type=mime_type,
        file_size_bytes=len(file_bytes),
        sort_order=existing_count,
        version=1,
    )
    db.add(image)
    db.commit()
    invalidate_public_catalog_if_published(item.id, current_status)
    db.refresh(image)
    return _serialize_item_image(image)


@router.put("/{item_id}/images/{image_id}/replace", response_model=ItemImageRead)
async def replace_item_image(
    item_id: UUID,
    image_id: UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = _get_owned_item(db, item_id, current_user.id)
    current_status = item.status
    _ensure_image_replace_allowed(item)

    image = db.query(ItemImage).filter(ItemImage.id == image_id, ItemImage.item_id == item.id).first()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")

    old_version = image.version
    old_storage_path = image.storage_path
    old_url = image.url

    file_bytes = await file.read()
    mime_type, ext = _validate_image_upload(file, file_bytes)

    storage = SupabaseStorageService()
    try:
        uploaded = storage.upload_bytes(str(item.id), file_bytes=file_bytes, extension=ext, mime_type=mime_type)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to upload replacement image to storage: {exc}") from exc

    image.url = uploaded.public_url
    image.storage_path = uploaded.storage_path
    image.mime_type = mime_type
    image.file_size_bytes = len(file_bytes)
    image.version = image.version + 1

    db.add(image)
    db.commit()
    invalidate_public_catalog_if_published(item.id, current_status)
    db.refresh(image)

    logger.info(
        "Item image replaced: item_id=%s image_id=%s status=%s old_version=%s new_version=%s old_url=%s new_url=%s",
        item.id,
        image.id,
        current_status,
        old_version,
        image.version,
        old_url,
        image.url,
    )

    try:
        storage.remove_file(old_storage_path)
    except Exception:
        logger.warning(
            "Failed to remove old image file after replace: item_id=%s image_id=%s storage_path=%s",
            item.id,
            image.id,
            old_storage_path,
        )

    return _serialize_item_image(image)


@router.delete("/{item_id}/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item_image(
    item_id: UUID,
    image_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = _get_owned_item(db, item_id, current_user.id)
    current_status = item.status
    _ensure_item_editable(item)

    image = db.query(ItemImage).filter(ItemImage.id == image_id, ItemImage.item_id == item.id).first()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")

    storage = SupabaseStorageService()
    try:
        storage.remove_file(image.storage_path)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to delete image from storage: {exc}") from exc

    db.delete(image)
    db.commit()
    invalidate_public_catalog_if_published(item.id, current_status)
    return None