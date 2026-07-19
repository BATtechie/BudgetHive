import ssl
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "BudgetHive"
    DEBUG: bool = True
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/budgethive"

    # Auth / JWT
    JWT_SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    GEMINI_API_KEY: str = "your_gemini_api_key_here"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def async_database_url(self) -> str:
        """Return an asyncpg-compatible SQLAlchemy URL without unsupported SSL params."""
        url = self.DATABASE_URL
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

        base, _, query_str = url.partition("?")
        if not query_str:
            return url

        query = parse_qsl(query_str, keep_blank_values=True)
        cleaned_query = [(k, v) for k, v in query if k not in {"sslmode", "channel_binding"}]
        cleaned_query_str = urlencode(cleaned_query)
        return f"{base}?{cleaned_query_str}" if cleaned_query_str else base

    @property
    def async_connect_args(self) -> dict:
        """Add SSL connect arguments when the URL uses Neon-style SSL query params."""
        parsed = urlparse(self.DATABASE_URL)
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        if "sslmode" in query or "channel_binding" in query:
            ssl_context = ssl.create_default_context()
            return {"ssl": ssl_context}
        return {}


settings = Settings() 