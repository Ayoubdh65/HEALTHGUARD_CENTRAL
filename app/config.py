"""
HealthGuard Central Server – Configuration.

Reads from environment variables (set in Render dashboard).
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Central server settings loaded from environment variables."""

    # ── Database (Render provides this automatically) ───────────────────
    DATABASE_URL: str = "postgresql+asyncpg://localhost/healthguard_central"

    # ── Security ────────────────────────────────────────────────────────
    # API keys that edge nodes use to authenticate.
    # Comma-separated list, e.g. "key1,key2,key3"
    ALLOWED_API_KEYS: str = "dev-test-key"

    # ── Server ──────────────────────────────────────────────────────────
    HOST: str = "0.0.0.0"
    PORT: int = 10000  # Render default port

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }

    @property
    def api_keys_list(self) -> list[str]:
        """Parse comma-separated API keys into a list."""
        return [k.strip() for k in self.ALLOWED_API_KEYS.split(",") if k.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
