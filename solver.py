from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from calendar_utils import is_saturday, is_sunday, iter_dates, month_range
from domain import Assignment, MonthInput, SLOT_TO_KIND
from jp_holidays import jp_holidays_in_month


class SolveError(RuntimeError):
    pass


@dataclass(frozen=True)
class SolveResult:
    assignments: tuple[Assignment, ...]


def _open_days(mi: MonthInput) -> list[date]:
    start, end = month_range(mi.month)
    closed = set(mi.closed_dates)
    jp_holidays = (
        set(jp_holidays_in_month(mi.month).keys()) if mi.auto_close_jp_holidays else set()
    )

    days: list[date] = []
    for d in iter_dates(start, end):
        if is_sunday(d):
            continue
        if d in jp_holidays:
            continue
        if d in closed:
            continue
        days.append(d)
    return days


def solve(mi: MonthInput) -> SolveResult:
    try:
        return _solve_with_ortools(mi)
    except ModuleNotFoundError as e:
        raise SolveError(
            "ortools が見つかりません。`pip install -r requirements.txt` を実行してください。"
        ) from e


def _solve_with_ortools(mi: MonthInput) -> SolveResult:
    from ortools.sat.python import cp_model

    staff = list(mi.staff)
    if not staff:
        raise SolveError("スタッフが0人です。")

    staff_ids = [s.id for s in staff]
    staff_index = {sid: i for i, sid in enumerate(staff_ids)}
    managers = {s.id for s in staff if s.is_manager}
    if not managers:
        raise SolveError("マネージャースキル保有者が0人です。")

    days = _open_days(mi)
    if not days:
        raise SolveError("営業日が0日です。祝日/休業日設定を確認してください。")

    req = mi.requirements

    # Slot templates:
    # - Weekday: early(1), A(1-2), B(2), B+(1)  -> total 5-6
    # - Saturday: early(1), A(2-3), B(2)       -> total 5-6
    def day_slots(d: date) -> list[tuple[str, bool]]:
        if is_saturday(d):
            return [
                ("sat_early", False),
                ("sat_a1", False),
                ("sat_a2", False),
                ("sat_a3", True),  # optional (2-3)
                ("sat_b1", False),
                ("sat_b2", False),
            ]
        return [
            ("wd_early", False),
            ("wd_a1", False),
            ("wd_a2", True),  # optional (1-2)
            ("wd_b1", False),
            ("wd_b2", False),
            ("wd_bplus", False),
        ]

    model = cp_model.CpModel()

    # Flatten to (day_index, slot_name).
    slot_keys: list[tuple[int, str]] = []
    slot_optional: dict[tuple[int, str], bool] = {}
    day_to_slots: dict[int, list[str]] = {}
    for di, d in enumerate(days):
        day_to_slots[di] = []
        for slot_name, is_opt in day_slots(d):
            key = (di, slot_name)
            slot_keys.append(key)
            slot_optional[key] = is_opt
            day_to_slots[di].append(slot_name)

    # active[di, slot] == 1 if that slot is used (mandatory slots are constant 1).
    active: dict[tuple[int, str], cp_model.IntVar] = {}
    for key in slot_keys:
        if slot_optional[key]:
            active[key] = model.NewBoolVar(f"active_d{key[0]}_{key[1]}")
        else:
            active[key] = model.NewConstant(1)

    # x[p, di, slot] == 1 if person p works that day in that slot.
    x: dict[tuple[int, int, str], cp_model.IntVar] = {}
    for p in range(len(staff)):
        for di, slot_name in slot_keys:
            x[(p, di, slot_name)] = model.NewBoolVar(f"x_p{p}_d{di}_{slot_name}")

    # Each slot filled by exactly one person if active, else nobody.
    for di, slot_name in slot_keys:
        model.Add(sum(x[(p, di, slot_name)] for p in range(len(staff))) == active[(di, slot_name)])

    # Each person works at most one slot per day.
    for p in range(len(staff)):
        for di in range(len(days)):
            model.Add(sum(x[(p, di, slot_name)] for slot_name in day_to_slots[di]) <= 1)

    # Requests off are hard constraints.
    for sid, offs in mi.requests_off.items():
        if sid not in staff_index:
            raise SolveError(f"requests_off に未知の staff id があります: {sid}")
        p = staff_index[sid]
        off_set = set(offs)
        for di, d in enumerate(days):
            if d in off_set:
                for slot_name in day_to_slots[di]:
                    model.Add(x[(p, di, slot_name)] == 0)

    # Per-staff allowed shift kinds (employment constraint).
    for p, s in enumerate(staff):
        if not s.allowed_kinds:
            continue
        allowed = set(s.allowed_kinds)
        for di, slot_name in slot_keys:
            kind = SLOT_TO_KIND.get(slot_name)
            if kind is None:
                raise SolveError(f"未知の slot_name です: {slot_name}")
            if kind not in allowed:
                model.Add(x[(p, di, slot_name)] == 0)

    # Saturday max per person (<= 3 days).
    for p in range(len(staff)):
        sat_work = []
        for di, d in enumerate(days):
            if is_saturday(d):
                sat_work.append(sum(x[(p, di, slot_name)] for slot_name in day_to_slots[di]))
        if sat_work:
            model.Add(sum(sat_work) <= req.saturday_max_per_person)

    # At least 1 manager each open day (any slot kind).
    for di in range(len(days)):
        manager_work = []
        for p, s in enumerate(staff):
            if s.id in managers:
                manager_work.append(sum(x[(p, di, slot_name)] for slot_name in day_to_slots[di]))
        model.Add(sum(manager_work) >= 1)

    # Objective:
    # 1) prefer max headcount (fill optional slots) unless impossible
    # 2) fairness: minimize spread in total workdays
    optional_keys = [k for k in slot_keys if slot_optional[k]]
    max_optional = len(optional_keys)

    totals: list[cp_model.IntVar] = []
    for p in range(len(staff)):
        v = model.NewIntVar(0, len(days), f"total_p{p}")
        model.Add(v == sum(x[(p, di, slot_name)] for (di, slot_name) in slot_keys))
        totals.append(v)

    max_total = model.NewIntVar(0, len(days), "max_total")
    min_total = model.NewIntVar(0, len(days), "min_total")
    model.AddMaxEquality(max_total, totals)
    model.AddMinEquality(min_total, totals)

    diffs: list[cp_model.IntVar] = []
    total_assigned = model.NewIntVar(0, len(slot_keys), "total_assigned")
    model.Add(total_assigned == sum(active[k] for k in slot_keys))
    avg = model.NewIntVar(0, len(days), "avg")
    model.AddDivisionEquality(avg, total_assigned, len(staff))

    for p, v in enumerate(totals):
        diff = model.NewIntVar(0, len(days), f"absdiff_p{p}")
        model.AddAbsEquality(diff, v - avg)
        diffs.append(diff)

    objective = (max_total - min_total) * 1000 + sum(diffs)
    if req.prefer_max_headcount and max_optional:
        filled_optional = sum(active[k] for k in optional_keys)
        unfilled = model.NewIntVar(0, max_optional, "unfilled_optional")
        model.Add(unfilled == max_optional - filled_optional)
        objective = unfilled * 1_000_000 + objective

    model.Minimize(objective)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10.0
    solver.parameters.num_search_workers = 8

    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise SolveError("条件を満たすシフトを作れませんでした。希望休や土曜上限を見直してください。")

    assignments: list[Assignment] = []
    for di, d in enumerate(days):
        slots_out: dict[str, str] = {}
        for slot_name in day_to_slots[di]:
            if solver.Value(active[(di, slot_name)]) == 0:
                continue
            chosen = None
            for p in range(len(staff)):
                if solver.Value(x[(p, di, slot_name)]) == 1:
                    chosen = staff[p].id
                    break
            if chosen is None:
                raise SolveError("内部エラー: slot が未割当です。")
            slots_out[slot_name] = chosen
        assignments.append(Assignment(day=d, slots=slots_out))

    return SolveResult(assignments=tuple(assignments))
