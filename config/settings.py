"""Central settings. Credentials come from environment variables / .env, never from source code."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_dotenv(path: Path) -> None:
    """Minimal .env reader (no extra dependency). Existing environment variables win."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    storage_dir: Path = ROOT / "storage"
    upload_dir: Path = ROOT / "storage" / "uploads"
    cache_dir: Path = ROOT / "storage" / "cache"
    models_dir: Path = ROOT / "assets" / "models"
    http_timeout_s: float = 8.0
    nasa_api_key: str = field(default_factory=lambda: os.getenv("NASA_API_KEY", ""))
    earthdata_user: str = field(default_factory=lambda: os.getenv("NASA_EARTHDATA_USERNAME", ""))
    earthdata_password: str = field(default_factory=lambda: os.getenv("NASA_EARTHDATA_PASSWORD", ""))
    copernicus_id: str = field(default_factory=lambda: os.getenv("COPERNICUS_CLIENT_ID", ""))
    copernicus_secret: str = field(default_factory=lambda: os.getenv("COPERNICUS_CLIENT_SECRET", ""))
    isro_key: str = field(default_factory=lambda: os.getenv("ISRO_API_KEY", ""))
    openai_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", ""))


def get_settings() -> Settings:
    s = Settings()
    for d in (s.storage_dir, s.upload_dir, s.cache_dir):
        d.mkdir(parents=True, exist_ok=True)
    return s
