from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    grpc_host: str
    grpc_port: int

    service_api_key: str
    redis_url: str = "redis://redis:6379/0"
    
    flight_cache_ttl_seconds: int = 300
    search_cache_ttl_seconds: int = 300

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()