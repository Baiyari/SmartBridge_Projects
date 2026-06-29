import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    # Local Ollama LLM settings — no API key needed
    ollama_model: str = "mistral"
    ollama_base_url: str = "http://localhost:11434"
    ollama_max_tokens: int = 1024

    sheets_credentials_path: str = field(default_factory=lambda: os.getenv("GOOGLE_SHEETS_CREDENTIALS", "credentials.json"))
    sheets_worksheet_name: str = "SEO Audit"

    # Google Sheet ID — read from .env
    google_sheet_id: str = field(default_factory=lambda: os.getenv("GOOGLE_SHEET_ID", ""))

    max_pages: int = 5
    crawl_timeout: int = 10
    max_concurrent: int = 20
    user_agent: str = "SEOAuditAgent/1.0"

    title_min: int = 30
    title_max: int = 65

    keyword_min_length: int = 3
    keyword_top_n: int = 10
    density_overuse: float = 0.04
    density_underuse: float = 0.005

    readability_min: float = 50.0

    link_timeout: int = 8
    max_redirects: int = 3


settings = Settings()