from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
    env_file="../.env",
    case_sensitive=False,
    extra="ignore",
    )

    project_name: str = "dropoff"
    environment: str = "local"

    postgres_server: str = "db"
    postgres_port: int = 5432
    postgres_db: str = "dropoff"
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    database_url: str

    secret_key: str
    access_token_expire_minutes: int = 60

    backend_cors_origins: str = "http://localhost:3000"
    frontend_url: str = "http://localhost:3000"

    smtp_host: str = "mailpit"
    smtp_port: int = 1025
    smtp_from: str = "no-reply@dropoff.local"

    pgadmin_default_email: str = "admin@example.com"
    pgadmin_default_password: str = "admin"

    supabase_url: str | None = None
    supabase_service_role_key: str | None = None
    supabase_storage_bucket: str = "item-images"
    supabase_storage_public_base_url: str | None = None

    max_item_image_count: int = 5
    max_item_image_size_bytes: int = 5 * 1024 * 1024
    allowed_item_image_mime_types: str = "image/jpeg,image/png,image/webp"

    @property
    def cors_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.backend_cors_origins.split(",")
            if origin.strip()
        ]

    @property
    def DATABASE_URL(self) -> str:
        return self.database_url

    @property
    def MAX_ITEM_IMAGE_COUNT(self) -> int:
        return self.max_item_image_count

    @property
    def MAX_ITEM_IMAGE_SIZE_BYTES(self) -> int:
        return self.max_item_image_size_bytes

    @property
    def ALLOWED_ITEM_IMAGE_MIME_TYPES(self) -> list[str]:
        return [
            mime.strip()
            for mime in self.allowed_item_image_mime_types.split(",")
            if mime.strip()
        ]

    @property
    def SUPABASE_URL(self) -> str | None:
        return self.supabase_url

    @property
    def SUPABASE_SERVICE_ROLE_KEY(self) -> str | None:
        return self.supabase_service_role_key

    @property
    def SUPABASE_STORAGE_BUCKET(self) -> str:
        return self.supabase_storage_bucket

    @property
    def SUPABASE_STORAGE_PUBLIC_BASE_URL(self) -> str | None:
        return self.supabase_storage_public_base_url


settings = Settings()