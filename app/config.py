from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./data/dsadps.db"
    jwt_secret: str = "development-only-change-me"
    admin_username: str = "admin"
    admin_password: str = "change-me"
    # Reserved for the optional SRS email-alert integration.
    smtp_host: str = ""
    smtp_port: int = 587
    # SRS-tunable values: keep them in configuration, not source code.
    rapid_submission_limit: int = 3
    rapid_submission_window_seconds: int = 60
    flood_window_seconds: int = 300
    flood_batch_limit: int = 700
    high_risk_threshold: int = 80
    captcha_threshold: int = 40
    # Google Gemini API key for the admin AI chatbot.
    gemini_api_key: str = ""
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)


settings = Settings()
