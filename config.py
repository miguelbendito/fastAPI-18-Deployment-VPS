from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    secret_key: SecretStr
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    max_upload_size_bytes: int = 5 * 1024 * 1024  # 5 MB
    posts_per_page: int = 10
    reset_token_expire_minutes: int = 60 #1 hour
    mail_server: str = "localhost"
    mail_port: int = 587
    mail_username: str = ""
    mail_password: SecretStr = SecretStr("")
    mail_from: str = "noreply@example.com"
    mail_use_tls: bool = True
    mail_validate_certs: bool = True
    database_url: str 

    frontend_url: str = "http://localhost:8000"
    s3_bucket_name: str
    s3_region: str = "us-east-2"
    s3_access_key_id: SecretStr | None = None
    s3_secret_access_key: SecretStr | None = None
    s3_endpoint_url: str | None = None

settings = Settings() # type: ignore[call-arg] # Load settings from .env file and environment variables