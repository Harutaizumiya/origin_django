import os
import sys
from pathlib import Path

from common.env import build_postgres_database_config, get_database_url

BASE_DIR = Path(__file__).resolve().parent.parent


def list_from_env(name: str, default: list[str]) -> list[str]:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return [item.strip() for item in raw.split(",") if item.strip()]


def bool_from_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


DATABASE_URL = get_database_url()
SECRET_KEY = "dev-secret-key"
DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "inventory",
    "accounts",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

if "test" in sys.argv:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "test.sqlite3",
        }
    }
else:
    DATABASES = {"default": build_postgres_database_config(DATABASE_URL)}

LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = list_from_env(
    "CORS_ALLOWED_ORIGINS",
    ["http://localhost:3000", "http://127.0.0.1:3000"],
)
CSRF_TRUSTED_ORIGINS = list_from_env(
    "CSRF_TRUSTED_ORIGINS",
    ["http://localhost:3000", "http://127.0.0.1:3000"],
)
QR_SCAN_NEAR_EXPIRY_DAYS = 7
QR_TOKEN_PEPPER = os.environ.get("QR_TOKEN_PEPPER") or SECRET_KEY
AUTH_TOKEN_PEPPER = os.environ.get("AUTH_TOKEN_PEPPER") or SECRET_KEY
AUTH_TOKEN_COOKIE_NAME = os.environ.get("AUTH_TOKEN_COOKIE_NAME", "origin_auth_token")
AUTH_TOKEN_COOKIE_PATH = os.environ.get("AUTH_TOKEN_COOKIE_PATH", "/api")
AUTH_TOKEN_COOKIE_SAMESITE = os.environ.get("AUTH_TOKEN_COOKIE_SAMESITE", "Lax")
AUTH_TOKEN_COOKIE_SECURE = bool_from_env("AUTH_TOKEN_COOKIE_SECURE", True)
CSRF_COOKIE_SECURE = bool_from_env("CSRF_COOKIE_SECURE", AUTH_TOKEN_COOKIE_SECURE)
CSRF_COOKIE_SAMESITE = os.environ.get("CSRF_COOKIE_SAMESITE", "Lax")
CSRF_COOKIE_HTTPONLY = False

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "accounts.authentication.CookieTokenAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
        "accounts.permissions.ComponentPermission",
    ],
}
