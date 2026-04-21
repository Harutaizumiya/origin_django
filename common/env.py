from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv


def load_project_env() -> None:
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ImproperlyConfigured(f"Missing required environment variable: {name}")
    return value


def get_database_url() -> str:
    load_project_env()
    return get_required_env("DATABASE_URL")


def build_postgres_database_config(database_url: str) -> dict[str, object]:
    parsed = urlparse(database_url)
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise ImproperlyConfigured("DATABASE_URL must use a postgres scheme")

    options: dict[str, str] = {}
    sslmode = parse_qs(parsed.query).get("sslmode", [None])[0]
    if sslmode:
        options["sslmode"] = sslmode

    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": parsed.path.lstrip("/"),
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname or "",
        "PORT": parsed.port or "",
        "OPTIONS": options,
    }
