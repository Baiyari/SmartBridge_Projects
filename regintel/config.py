"""
Central configuration for RegIntel.

All runtime settings are loaded from environment variables (via a local
.env file) so that no secrets are ever hard-coded into source files.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Load variables from a .env file in the project root, if present.
load_dotenv(override=True)

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
CIRCULARS_DIR = DATA_DIR / "circulars"
POLICIES_DIR = DATA_DIR / "policies"
REPORTS_DIR = PROJECT_ROOT / "outputs" / "reports"

for _dir in (CIRCULARS_DIR, POLICIES_DIR, REPORTS_DIR):
    _dir.mkdir(parents=True, exist_ok=True)


def _require_env(name: str) -> str:
    """Fetch a required environment variable or raise a clear error."""
    value = os.getenv(name)
    if not value or value.startswith("your_"):
        raise EnvironmentError(
            f"Missing required environment variable '{name}'. "
            f"Copy .env.example to .env and set a valid value."
        )
    return value


@dataclass(frozen=True)
class Settings:
    groq_api_key: str
    groq_model: str
    chroma_persist_dir: str
    embedding_model: str

    @classmethod
    def load(cls) -> "Settings":
        return cls(
            groq_api_key=_require_env("GROQ_API_KEY"),
            groq_model=os.getenv("GROQ_MODEL", "qwen/qwen3.6-27b"),
            chroma_persist_dir=os.getenv("CHROMA_PERSIST_DIR", "data/chroma_db"),
            embedding_model=os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2"),
        )


def get_settings() -> Settings:
    """Lazily build a Settings instance. Call this, don't import a singleton,
    so that errors surface only when configuration is actually needed
    (e.g. unit tests that don't touch Groq can still import this module)."""
    return Settings.load()