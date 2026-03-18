from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_host: str
    app_port: int

    database_url: str

    flight_service_host: str
    flight_service_port: int = 50051
    flight_service_api_key: str

    grpc_timeout_seconds: float = 3.0
    grpc_retry_max_attempts: int = 3
    grpc_retry_initial_backoff_ms: int = 100

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()