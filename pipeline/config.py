"""Pipeline configuration."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


class Config(BaseSettings):
    """Pipeline configuration from environment."""

    # Database
    db_path: Path = Path("data/j1_principles.db")

    # Content-addressable storage
    cas_dir: Path = Path("data/objects")

    # Logging
    log_dir: Path = Path("data/logs")
    log_level: str = "INFO"

    # API keys
    gemini_api_key: str = Field(
        default="",
        min_length=1,
        description="Required: Gemini API key from https://aistudio.google.com"
    )

    # LLM settings
    gemini_model: str = "gemini-3-flash-preview"
    max_retries: int = 3
    timeout_seconds: int = 60

    # Extraction settings
    chunk_size: int = 1000
    chunk_overlap: int = 200
    fuzzy_threshold: float = 90.0
    min_confidence: float = 0.5

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


# Global config instance
config = Config()
