from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://plumb:plumb_dev@localhost:5432/plumb"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # S3 / MinIO
    S3_ENDPOINT_URL: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "plumb"
    S3_SECRET_KEY: str = "plumb_dev_key"
    S3_BUCKET_NAME: str = "plumb-documents"
    S3_REGION: str = "us-east-1"

    # Auth
    JWT_SECRET: str = "change-me-in-production-use-a-real-secret"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_MINUTES: int = 1440

    # Anthropic
    ANTHROPIC_API_KEY: str = ""

    # NYC Public Data (Socrata)
    SOCRATA_APP_TOKEN: str = ""

    # Brave Search
    BRAVE_API_KEY: str = ""

    # Gmail (email integration for demo)
    GMAIL_CREDENTIALS_JSON: str = ""  # Path to OAuth2 credentials.json
    GMAIL_TOKEN_JSON: str = ""  # Path to stored token.json
    GMAIL_MONITORED_ADDRESS: str = ""  # e.g. deals@plumb.ai
    GMAIL_LABEL: str = "plumb"  # Only emails with this Gmail label trigger the workflow
    GMAIL_POLL_INTERVAL_SECONDS: int = 30
    GMAIL_ENABLED: bool = False

    @property
    def SYNC_DATABASE_URL(self) -> str:
        """Sync database URL for Celery workers (psycopg2)."""
        return self.DATABASE_URL.replace("+asyncpg", "").replace(
            "postgresql://", "postgresql+psycopg2://"
        )

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
