from __future__ import annotations
from datetime import date


def rel_date(iso_date: str | None) -> str:
    if not iso_date:
        return "—"
    try:
        d = date.fromisoformat(iso_date[:10])
    except (ValueError, TypeError):
        return iso_date
    delta = (date.today() - d).days
    if delta == 0:
        return "hoje"
    if delta == 1:
        return "ontem"
    if delta < 7:
        return f"{delta}d atrás"
    if delta < 30:
        return f"{delta // 7}sem atrás"
    if delta < 365:
        return f"{delta // 30}m atrás"
    return f"{delta // 365}a atrás"
