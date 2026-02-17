from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable, Mapping


KIND_WD_EARLY = "wd_early"
KIND_WD_A = "wd_a"
KIND_WD_B = "wd_b"
KIND_WD_BPLUS = "wd_bplus"
KIND_SAT_EARLY = "sat_early"
KIND_SAT_A = "sat_a"
KIND_SAT_B = "sat_b"


SLOT_WD_EARLY = "wd_early"
SLOT_WD_A1 = "wd_a1"
SLOT_WD_A2 = "wd_a2"  # optional
SLOT_WD_B1 = "wd_b1"
SLOT_WD_B2 = "wd_b2"
SLOT_WD_BPLUS = "wd_bplus"

SLOT_SAT_EARLY = "sat_early"
SLOT_SAT_A1 = "sat_a1"
SLOT_SAT_A2 = "sat_a2"
SLOT_SAT_A3 = "sat_a3"  # optional
SLOT_SAT_B1 = "sat_b1"
SLOT_SAT_B2 = "sat_b2"


SLOT_ORDER = (
    SLOT_WD_EARLY,
    SLOT_WD_A1,
    SLOT_WD_A2,
    SLOT_WD_B1,
    SLOT_WD_B2,
    SLOT_WD_BPLUS,
    SLOT_SAT_EARLY,
    SLOT_SAT_A1,
    SLOT_SAT_A2,
    SLOT_SAT_A3,
    SLOT_SAT_B1,
    SLOT_SAT_B2,
)


SLOT_LABEL_JA = {
    SLOT_WD_EARLY: "平日早番",
    SLOT_WD_A1: "平日A(1)",
    SLOT_WD_A2: "平日A(2)",
    SLOT_WD_B1: "平日B(1)",
    SLOT_WD_B2: "平日B(2)",
    SLOT_WD_BPLUS: "平日B+",
    SLOT_SAT_EARLY: "土曜早番",
    SLOT_SAT_A1: "土曜A(1)",
    SLOT_SAT_A2: "土曜A(2)",
    SLOT_SAT_A3: "土曜A(3)",
    SLOT_SAT_B1: "土曜B(1)",
    SLOT_SAT_B2: "土曜B(2)",
}


SLOT_TO_KIND = {
    SLOT_WD_EARLY: KIND_WD_EARLY,
    SLOT_WD_A1: KIND_WD_A,
    SLOT_WD_A2: KIND_WD_A,
    SLOT_WD_B1: KIND_WD_B,
    SLOT_WD_B2: KIND_WD_B,
    SLOT_WD_BPLUS: KIND_WD_BPLUS,
    SLOT_SAT_EARLY: KIND_SAT_EARLY,
    SLOT_SAT_A1: KIND_SAT_A,
    SLOT_SAT_A2: KIND_SAT_A,
    SLOT_SAT_A3: KIND_SAT_A,
    SLOT_SAT_B1: KIND_SAT_B,
    SLOT_SAT_B2: KIND_SAT_B,
}


@dataclass(frozen=True)
class Staff:
    id: str
    name: str
    is_manager: bool = False
    allowed_kinds: tuple[str, ...] | None = None  # None means "all kinds allowed"


@dataclass(frozen=True)
class Requirements:
    saturday_max_per_person: int = 3
    prefer_max_headcount: bool = True  # try to fill optional slots if feasible


@dataclass(frozen=True)
class MonthInput:
    month: str  # "YYYY-MM"
    staff: tuple[Staff, ...]
    closed_dates: tuple[date, ...]
    requests_off: Mapping[str, tuple[date, ...]]  # staff_id -> dates
    requirements: Requirements = Requirements()
    auto_close_jp_holidays: bool = True

    def staff_by_id(self) -> dict[str, Staff]:
        return {s.id: s for s in self.staff}


@dataclass(frozen=True)
class Assignment:
    day: date
    slots: Mapping[str, str]  # slot_name -> staff_id (missing means unassigned/unused)

    def all_staff_ids(self) -> Iterable[str]:
        yield from self.slots.values()
