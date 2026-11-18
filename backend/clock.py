"""Time source. Isolated so tests and demo seeding can control 'today'."""
from datetime import date, datetime

_override = None  # date | None


def set_today(d):
    global _override
    _override = d


def today() -> date:
    return _override or date.today()


def now_iso() -> str:
    n = datetime.now().replace(microsecond=0)
    if _override:
        n = n.replace(year=_override.year, month=_override.month, day=_override.day)
    return n.isoformat(sep=" ")
