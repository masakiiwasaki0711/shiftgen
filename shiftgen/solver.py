from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .calendar_utils import is_saturday, is_sunday, iter_dates, month_range
from .domain import Assignment, MonthInput, SLOT_TO_KIND
from .jp_holidays import jp_holidays_in_month


class SolveError(RuntimeError):
    pass


class _InfeasibleError(Exception):
    """厳格制約で解なしのとき内部的に送出し、緩和モードへの切り替えに使う。"""
    pass


@dataclass(frozen=True)
class SolveResult:
    assignments: tuple[Assignment, ...]
    is_partial: bool = False  # True のとき制約緩和モードで生成（空きスロットあり）


def _open_days(mi: MonthInput) -> list[date]:
    start, end = month_range(mi.month)
    closed = set(mi.closed_dates)
    jp_holidays = set(jp_holidays_in_month(mi.month).keys()) if mi.auto_close_jp_holidays else set()

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
    """まず厳格制約で解を求め、不可能なら制約緩和モードで再挑戦する。"""
    try:
        try:
            return _solve_with_ortools(mi, relaxed=False)
        except _InfeasibleError:
            return _solve_with_ortools(mi, relaxed=True)
    except ModuleNotFoundError as e:
        raise SolveError(
            "ortools が見つかりません。`pip install -r requirements.txt` を実行してください。"
        ) from e


def _solve_with_ortools(mi: MonthInput, relaxed: bool = False) -> SolveResult:
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

    # Weekday: early(1), A(1-2), B(2), B+(1) -> 5-6
    # Saturday: early(1), A(2-3), B(2)      -> 5-6
    def day_slots(d: date) -> list[tuple[str, bool]]:
        if is_saturday(d):
            return [
                ("sat_early", False),
                ("sat_a1", False),
                ("sat_a2", False),
                ("sat_a3", True),
                ("sat_b1", False),
                ("sat_b2", False),
            ]
        return [
            ("wd_early", False),
            ("wd_a1", False),
            ("wd_a2", True),
            ("wd_b1", False),
            ("wd_b2", False),
            ("wd_bplus", False),
        ]

    model = cp_model.CpModel()

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

    # 緩和モードでは必須スロットも任意（空き可）にする
    active: dict[tuple[int, str], cp_model.IntVar] = {}
    for key in slot_keys:
        if slot_optional[key] or relaxed:
            active[key] = model.NewBoolVar(f"active_d{key[0]}_{key[1]}")
        else:
            active[key] = model.NewConstant(1)

    x: dict[tuple[int, int, str], cp_model.IntVar] = {}
    for p in range(len(staff)):
        for di, slot_name in slot_keys:
            x[(p, di, slot_name)] = model.NewBoolVar(f"x_p{p}_d{di}_{slot_name}")

    for di, slot_name in slot_keys:
        model.Add(sum(x[(p, di, slot_name)] for p in range(len(staff))) == active[(di, slot_name)])

    for p in range(len(staff)):
        for di in range(len(days)):
            model.Add(sum(x[(p, di, slot_name)] for slot_name in day_to_slots[di]) <= 1)

    # 希望休・種別制限は緩和モードでも常にハード制約
    for sid, offs in mi.requests_off.items():
        if sid not in staff_index:
            raise SolveError(f"requests_off に未知の staff id があります: {sid}")
        p = staff_index[sid]
        off_set = set(offs)
        for di, d in enumerate(days):
            if d in off_set:
                for slot_name in day_to_slots[di]:
                    model.Add(x[(p, di, slot_name)] == 0)

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

    # 土曜出勤上限
    sat_excess_vars: list[cp_model.IntVar] = []
    for p in range(len(staff)):
        sat_work = []
        for di, d in enumerate(days):
            if is_saturday(d):
                sat_work.append(sum(x[(p, di, slot_name)] for slot_name in day_to_slots[di]))
        if not sat_work:
            continue
        if relaxed:
            # ソフト制約: 超過分をペナルティ変数で捕捉
            excess = model.NewIntVar(0, len(sat_work), f"sat_excess_p{p}")
            model.Add(sum(sat_work) - req.saturday_max_per_person <= excess)
            sat_excess_vars.append(excess)
        else:
            model.Add(sum(sat_work) <= req.saturday_max_per_person)

    # マネージャー1日1人以上
    no_manager_vars: list[cp_model.IntVar] = []
    for di in range(len(days)):
        manager_work = []
        for p, s in enumerate(staff):
            if s.id in managers:
                manager_work.append(sum(x[(p, di, slot_name)] for slot_name in day_to_slots[di]))
        if relaxed:
            # ソフト制約: マネージャー不在日をペナルティ変数で捕捉
            no_mgr = model.NewBoolVar(f"no_mgr_d{di}")
            model.Add(sum(manager_work) == 0).OnlyEnforceIf(no_mgr)
            model.Add(sum(manager_work) >= 1).OnlyEnforceIf(no_mgr.Not())
            no_manager_vars.append(no_mgr)
        else:
            model.Add(sum(manager_work) >= 1)

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

    total_assigned = model.NewIntVar(0, len(slot_keys), "total_assigned")
    model.Add(total_assigned == sum(active[k] for k in slot_keys))
    avg = model.NewIntVar(0, len(days), "avg")
    model.AddDivisionEquality(avg, total_assigned, len(staff))

    diffs: list[cp_model.IntVar] = []
    for p, v in enumerate(totals):
        diff = model.NewIntVar(0, len(days), f"absdiff_p{p}")
        model.AddAbsEquality(diff, v - avg)
        diffs.append(diff)

    imbalance_obj = (max_total - min_total) * 1000 + sum(diffs)

    if relaxed:
        # 優先度(高→低):
        # 1. 必須スロットをなるべく埋める (1000万/未充填スロット)
        # 2. マネージャーが不在の日を減らす (100万/日)
        # 3. 土曜上限超過を減らす (1万/人-土曜)
        # 4. 勤務日数の均等化
        mandatory_keys = [k for k in slot_keys if not slot_optional[k]]
        unfilled_mandatory = model.NewIntVar(0, len(mandatory_keys), "unfilled_mandatory")
        model.Add(unfilled_mandatory == len(mandatory_keys) - sum(active[k] for k in mandatory_keys))

        objective = (
            unfilled_mandatory * 10_000_000
            + sum(no_manager_vars) * 1_000_000
            + sum(sat_excess_vars) * 10_000
            + imbalance_obj
        )
        if req.prefer_max_headcount and max_optional:
            filled_optional = sum(active[k] for k in optional_keys)
            unfilled_opt = model.NewIntVar(0, max_optional, "unfilled_optional")
            model.Add(unfilled_opt == max_optional - filled_optional)
            objective = objective + unfilled_opt * 1_000
    else:
        objective = imbalance_obj
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
        if relaxed:
            raise SolveError("制約を緩和しても解が見つかりませんでした。スタッフ数や希望休設定を見直してください。")
        raise _InfeasibleError()

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
                if not relaxed:
                    raise SolveError("内部エラー: slot が未割当です。")
                continue  # 緩和モードでは空きスロットをスキップ
            slots_out[slot_name] = chosen
        assignments.append(Assignment(day=d, slots=slots_out))

    return SolveResult(assignments=tuple(assignments), is_partial=relaxed)
