from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file.

    All agent code should obtain settings via `get_settings()` — never
    read environment variables directly.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── API keys ──────────────────────────────────────────────────────────────
    anthropic_api_key: str
    alpha_vantage_api_key: str = ""

    # ── Model selection (names must match Anthropic model IDs) ───────────────
    model_orchestrator: str = "claude-opus-4-6"
    model_analyst: str = "claude-sonnet-4-6"
    model_writer: str = "claude-sonnet-4-6"

    # ── Logging ───────────────────────────────────────────────────────────────
    log_level: str = "INFO"

    # ── Paths ─────────────────────────────────────────────────────────────────
    report_output_dir: Path = Path("outputs")
    watchlist_path: Path = Path("config/watchlist.yaml")

    def model_for_role(self, role: str) -> str:
        """Return the configured model ID for a given agent role name."""
        mapping = {
            "orchestrator": self.model_orchestrator,
            "analyst": self.model_analyst,
            "writer": self.model_writer,
        }
        return mapping.get(role, self.model_analyst)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the singleton Settings instance (cached after first call)."""
    return Settings()
