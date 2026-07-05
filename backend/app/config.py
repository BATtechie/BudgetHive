from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "BudgetHive"
    DEBUG: bool = True
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/budgethive"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
