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
    # Shared secret partner backends must send as X-API-Key to /v1/submissions.
    # Empty means the endpoint is disabled (fails closed, never open).
    submissions_api_key: str = ""
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)


settings = Settings()

# Placeholder values shipped in the code or in .env.example; never acceptable at runtime.
INSECURE_SECRETS = {"", "development-only-change-me", "replace-with-a-long-random-secret"}
INSECURE_PASSWORDS = {"", "change-me", "change-me-before-deploying"}


def validate_secrets(current: Settings = settings) -> None:
    """Refuse to start with default credentials (anyone could forge admin tokens)."""
    problems = []
    if current.jwt_secret in INSECURE_SECRETS:
        problems.append("JWT_SECRET is unset or a default placeholder")
    if current.admin_password in INSECURE_PASSWORDS:
        problems.append("ADMIN_PASSWORD is unset or a default placeholder")
    if problems:
        raise RuntimeError("Insecure configuration: " + "; ".join(problems) + ". Set strong values in .env and restart.")
