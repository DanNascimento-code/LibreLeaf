import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

SUPPORTED_MARKETS = ("BR", "US", "AR")


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime configuration loaded from environment variables."""

    contact_email: str | None = None
    timeout: float = 15.0
    max_retries: int = 2

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(Path(".env"), override=False)
        value = cls(
            contact_email=_optional_env("LIBRELEAF_CONTACT_EMAIL"),
        )
        if value.timeout <= 0 or value.max_retries < 0:
            raise ValueError("Invalid network settings")
        return value


def normalize_market(raw: str) -> str:
    market = raw.strip().upper()
    if market not in SUPPORTED_MARKETS:
        choices = ", ".join(SUPPORTED_MARKETS)
        raise ValueError(f"Unsupported market {raw!r}; choose {choices}")
    return market


def _optional_env(name: str) -> str | None:
    value = os.getenv(name, "").strip()
    return value or None
