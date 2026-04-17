import uuid
from dataclasses import dataclass

from supabase import Client, create_client

from app.core.config import settings


@dataclass
class UploadedImage:
    storage_path: str
    public_url: str


class SupabaseStorageService:
    def __init__(self) -> None:
        if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
            raise RuntimeError("Supabase storage is not configured. Check SUPABASE_* values in .env")

        self.bucket = settings.SUPABASE_STORAGE_BUCKET
        self.public_base_url = settings.SUPABASE_STORAGE_PUBLIC_BASE_URL.rstrip("/")
        self.client: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)

    def build_storage_path(self, item_id: str, extension: str) -> str:
        ext = extension.lower().lstrip(".") or "bin"
        return f"items/{item_id}/{uuid.uuid4().hex}.{ext}"

    def upload_bytes(self, item_id: str, file_bytes: bytes, extension: str, mime_type: str) -> UploadedImage:
        storage_path = self.build_storage_path(item_id=item_id, extension=extension)
        self.client.storage.from_(self.bucket).upload(
            path=storage_path,
            file=file_bytes,
            file_options={
                "content-type": mime_type,
                "cache-control": "31536000",
                "upsert": "false",
            },
        )
        response = self.client.storage.from_(self.bucket).get_public_url(storage_path)
        public_url = response if isinstance(response, str) else response.get("publicUrl") or response.get("public_url")
        if not public_url:
            public_url = f"{self.public_base_url}/{self.bucket}/{storage_path}"
        return UploadedImage(storage_path=storage_path, public_url=public_url)

    def remove_file(self, storage_path: str) -> None:
        self.client.storage.from_(self.bucket).remove([storage_path])