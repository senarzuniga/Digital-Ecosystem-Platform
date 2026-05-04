from pydantic_settings import BaseSettings, SettingsConfigDict

class ProdSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    SECRET_KEY: str = "prod-secret-key"
    # Add other production-specific settings here
