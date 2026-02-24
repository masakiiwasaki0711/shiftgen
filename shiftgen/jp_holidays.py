from __future__ import annotations

from datetime import date


def jp_holidays_in_month(month: str) -> dict[date, str]:
    """
    Returns {holiday_date: holiday_name} for Japan public holidays in the given YYYY-MM.
    Prefers `jpholiday` if installed; falls back to `holidays` if available.
    """
    year_s, mon_s = month.split("-")
    year = int(year_s)
    mon = int(mon_s)

    try:
        import jpholiday  # type: ignore

        out: dict[date, str] = {}
        mh = getattr(jpholiday, "month_holidays", None)
        if callable(mh):
            for d, name in mh(year, mon):
                out[d] = str(name)
            return out

        from calendar import monthrange

        last = monthrange(year, mon)[1]
        for day in range(1, last + 1):
            d = date(year, mon, day)
            name = jpholiday.is_holiday_name(d)
            if name:
                out[d] = str(name)
        return out
    except Exception:
        pass

    try:
        import holidays  # type: ignore

        jp = holidays.JP(years=[year])
        out = {}
        for d, name in jp.items():
            if isinstance(d, date) and d.year == year and d.month == mon:
                out[d] = str(name)
        return out
    except Exception:
        return {}

