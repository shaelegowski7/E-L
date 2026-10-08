"""Settings, read from the environment with the repo's .env as a fallback."""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
_KEYS = ("EL_VAULT", "EL_SANDBOX", "EL_HERMES_URL", "EL_HERMES_TOKEN")


def _read_dotenv(path: Path) -> dict[str, str]:
    """Read only the E-L keys from a .env file, so other secrets in it stay unread."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        key, sep, value = line.strip().partition("=")
        if sep and key.strip() in _KEYS:
            values[key.strip()] = value.strip().strip("\"'")
    return values


@dataclass(frozen=True)
class Settings:
    vault: Path
    sandbox: str
    hermes_url: str
    hermes_token: str | None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    dotenv = _read_dotenv(REPO / ".env")

    def get(key: str, default: str = "") -> str:
        return os.environ.get(key) or dotenv.get(key) or default

    vault = get("EL_VAULT")
    if not vault:
        raise RuntimeError("EL_VAULT is not set. Add it to .env (see .env.example).")
    return Settings(
        vault=Path(vault),
        sandbox=get("EL_SANDBOX", "e-l"),
        hermes_url=get("EL_HERMES_URL", "http://127.0.0.1:8642/v1").rstrip("/"),
        hermes_token=get("EL_HERMES_TOKEN") or None,
    )
