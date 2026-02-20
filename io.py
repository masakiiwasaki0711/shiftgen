from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date

from domain import MonthInput, Requirements, Staff


def _parse_date(d: str) -> date:
    y, m, dd = d.split("-")
    return date(int(y), int(m), int(dd))


def load_month_input_json(path: str) -> MonthInput:
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    staff = tuple(
        Staff(
            id=s["id"],
            name=s["name"],
            is_manager=bool(s.get("is_manager", False)),
            allowed_kinds=tuple(s["allowed_kinds"]) if s.get("allowed_kinds") else None,
        )
        for s in raw["staff"]
    )
    closed_dates = tuple(_parse_date(d) for d in raw.get("closed_dates", []))

    requests_off_raw = raw.get("requests_off", {})
    requests_off: dict[str, tuple[date, ...]] = {}
    for staff_id, dates in requests_off_raw.items():
        requests_off[staff_id] = tuple(_parse_date(d) for d in dates)

    req_raw = raw.get("requirements") or {}
    requirements = Requirements(
        saturday_max_per_person=int(req_raw.get("saturday_max_per_person", 3)),
        prefer_max_headcount=bool(req_raw.get("prefer_max_headcount", True)),
    )

    return MonthInput(
        month=str(raw["month"]),
        staff=staff,
        closed_dates=closed_dates,
        requests_off=requests_off,
        requirements=requirements,
        auto_close_jp_holidays=bool(raw.get("auto_close_jp_holidays", True)),
    )


def dump_month_input_json(mi: MonthInput) -> str:
    raw = {
        "month": mi.month,
        "auto_close_jp_holidays": mi.auto_close_jp_holidays,
        "closed_dates": [d.isoformat() for d in mi.closed_dates],
        "staff": [
            {
                "id": s.id,
                "name": s.name,
                "is_manager": s.is_manager,
                "allowed_kinds": list(s.allowed_kinds) if s.allowed_kinds else None,
            }
            for s in mi.staff
        ],
        "requests_off": {
            sid: [d.isoformat() for d in ds] for sid, ds in mi.requests_off.items()
        },
        "requirements": asdict(mi.requirements),
    }
    return json.dumps(raw, ensure_ascii=False, indent=2)
