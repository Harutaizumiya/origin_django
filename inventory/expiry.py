from __future__ import annotations

from datetime import date
from typing import Optional

from django.utils import timezone


EXPIRY_STATUS_EXPIRED = "expired"
EXPIRY_STATUS_CRITICAL = "critical"
EXPIRY_STATUS_WARNING = "warning"
EXPIRY_STATUS_NORMAL = "normal"
EXPIRY_STATUS_UNKNOWN = "unknown"

ALERT_EXPIRY_STATUSES = (
    EXPIRY_STATUS_EXPIRED,
    EXPIRY_STATUS_CRITICAL,
    EXPIRY_STATUS_WARNING,
)

VALID_EXPIRY_STATUSES = (
    EXPIRY_STATUS_EXPIRED,
    EXPIRY_STATUS_CRITICAL,
    EXPIRY_STATUS_WARNING,
    EXPIRY_STATUS_NORMAL,
)


def _today(today: Optional[date] = None) -> date:
    return today or timezone.localdate()


def _as_date(value) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value[:10])
    return None


def calc_days_until_expiry(expire_date: Optional[date], today: Optional[date] = None) -> Optional[int]:
    expire_date = _as_date(expire_date)
    if expire_date is None:
        return None
    return (expire_date - _today(today)).days


def calc_expiry_progress(
    manufacture_date: Optional[date],
    shelf_life_days: Optional[int],
    today: Optional[date] = None,
) -> Optional[float]:
    manufacture_date = _as_date(manufacture_date)
    if manufacture_date is None or shelf_life_days is None:
        return None
    if shelf_life_days <= 0:
        return 1.01

    elapsed_days = (_today(today) - manufacture_date).days
    return round(elapsed_days / shelf_life_days, 4)


def calc_expiry_status(
    manufacture_date: Optional[date],
    shelf_life_days: Optional[int],
    today: Optional[date] = None,
) -> str:
    progress = calc_expiry_progress(manufacture_date, shelf_life_days, today)

    if progress is None:
        return EXPIRY_STATUS_UNKNOWN
    if progress > 1.0:
        return EXPIRY_STATUS_EXPIRED
    if progress > 0.9:
        return EXPIRY_STATUS_CRITICAL
    if progress > 0.75:
        return EXPIRY_STATUS_WARNING
    return EXPIRY_STATUS_NORMAL
