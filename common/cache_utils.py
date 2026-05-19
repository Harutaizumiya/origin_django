from __future__ import annotations

from collections.abc import Callable
from hashlib import sha256

from django.conf import settings
from django.core.cache import cache


CACHE_GROUP_INVENTORY_READ = "inventory_read"
CACHE_GROUP_PRODUCT_CATEGORIES = "product_categories"
CACHE_GROUP_AUTH_PERMISSIONS = "auth_permissions"
CACHE_GROUP_AUTH_ROLES = "auth_roles"


def _version_key(group: str) -> str:
    return f"perf-cache-version:{group}"


def cache_timeout() -> int:
    return int(getattr(settings, "PERFORMANCE_CACHE_TIMEOUT", 30))


def cache_version(group: str) -> int:
    version = cache.get(_version_key(group))
    if version is None:
        version = 1
        cache.set(_version_key(group), version, None)
    return int(version)


def invalidate_cache_group(group: str) -> None:
    key = _version_key(group)
    try:
        cache.incr(key)
    except ValueError:
        cache.set(key, 2, None)


def invalidate_cache_groups(*groups: str) -> None:
    for group in groups:
        invalidate_cache_group(group)


def cached_value(group: str, identifier: str, factory: Callable[[], object], *, timeout: int | None = None):
    digest = sha256(identifier.encode("utf-8")).hexdigest()
    key = f"perf-cache:{group}:v{cache_version(group)}:{digest}"
    sentinel = object()
    value = cache.get(key, sentinel)
    if value is not sentinel:
        return value

    value = factory()
    cache.set(key, value, cache_timeout() if timeout is None else timeout)
    return value
