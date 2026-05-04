from pydantic_settings import BaseSettings, SettingsConfigDict

class DevSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    SECRET_KEY: str = "dev-secret-key"
    # Add other development-specific settings here
