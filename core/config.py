from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    Manages all application settings.
    Automatically reads variables from the .env file.
    """
    # Database settings
    DATABASE_URL: str

    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int

    # Redis settings
    REDIS_HOST: str 
    REDIS_PORT: int

    # some rate limiting constants 
    RATE_LIMIT_PER_HOUR: int
    USER_RATE_LIMIT_PER_HOUR: int
    MAX_FAILED_ATTEMPTS: int
    LOCKOUT_DURATION_SECONDS: int

    HEARTBEAT_INTERVAL_SECONDS: int
    USER_RATE_LIMIT_PER_HOUR: int

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",       # Ignores extra variables in .env
        case_sensitive=False  # Allows matching 'database_url' to 'DATABASE_URL'
    )

settings = Settings()