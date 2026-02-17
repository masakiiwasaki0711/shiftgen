from __future__ import annotations

import json
import tkinter as tk
from dataclasses import dataclass
from datetime import date
from tkinter import filedialog, messagebox, ttk

from .calendar_utils import iter_dates, month_range
from .domain import KIND_SAT_B, KIND_WD_A, MonthInput, Requirements, SLOT_LABEL_JA, SLOT_ORDER, Staff
from .excel import export_xlsx
from .jp_holidays import jp_holidays_in_month
from .solver import SolveError, solve
from .template_excel import export_template_xlsx, import_from_template_xlsx


def _parse_date(s: str) -> date:
    y, m, d = s.split("-")
    return date(int(y), int(m), int(d))


def _weekday_jp(d: date) -> str:
    return "月火水木金土日"[d.weekday()]


@dataclass
class UiState:
    month: str = "2026-02"
    requirements: Requirements = Requirements()
    staff: list[Staff] = None  # type: ignore[assignment]
    closed_dates: set[date] = None  # type: ignore[assignment]
    requests_off: dict[str, set[date]] = None  # type: ignore[assignment]
    auto_close_jp_holidays: bool = True

    def __post_init__(self):
        if self.staff is None:
            self.staff = []
        if self.closed_dates is None:
            self.closed_dates = set()
        if self.requests_off is None:
            self.requests_off = {}


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("shiftgen - シフト表自動作成")
        self.geometry("1100x700")

        self.state = UiState()
        self._jp_holidays: dict[date, str] = {}
        self._build_ui()

    def _build_ui(self):
        top = ttk.Frame(self)
        top.pack(fill="x", padx=10, pady=10)

        ttk.Label(top, text="対象月 (YYYY-MM)").pack(side="left")
        self.month_var = tk.StringVar(value=self.state.month)
        ttk.Entry(top, textvariable=self.month_var, width=10).pack(side="left", padx=8)
        ttk.Button(top, text="カレンダー更新", command=self._rebuild_calendar).pack(side="left")

        ttk.Button(top, text="サンプル読込", command=self._load_sample).pack(side="left", padx=8)
        ttk.Button(top, text="JSON読込", command=self._load_json).pack(side="left", padx=8)
        ttk.Button(top, text="JSON保存", command=self._save_json).pack(side="left", padx=8)
        ttk.Button(top, text="テンプレ読込(Excel)", command=self._load_template).pack(side="left", padx=8)
        ttk.Button(top, text="テンプレ出力(Excel)", command=self._save_template).pack(side="left", padx=8)

        mid = ttk.PanedWindow(self, orient="horizontal")
        mid.pack(fill="both", expand=True, padx=10, pady=10)

        left = ttk.Frame(mid)
        right = ttk.Frame(mid)
        mid.add(left, weight=1)
        mid.add(right, weight=2)

        self._build_staff_panel(left)
        self._build_calendar_panel(left)
        self._build_preview_panel(right)

        bottom = ttk.Frame(self)
        bottom.pack(fill="x", padx=10, pady=10)
        ttk.Button(bottom, text="生成", command=self._generate).pack(side="left")
        ttk.Button(bottom, text="Excel出力", command=self._export).pack(side="left", padx=10)
        self.status_var = tk.StringVar(value="入力して「生成」を押してください。")
        ttk.Label(bottom, textvariable=self.status_var).pack(side="left", padx=10)

    def _build_staff_panel(self, parent: ttk.Frame):
        box = ttk.Labelframe(parent, text="スタッフ (8人想定 / 追加・編集可)")
        box.pack(fill="x", pady=6)

        row = ttk.Frame(box)
        row.pack(fill="x", padx=8, pady=6)
        ttk.Label(row, text="ID").pack(side="left")
        self.staff_id_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.staff_id_var, width=8).pack(side="left", padx=6)
        ttk.Label(row, text="名前").pack(side="left")
        self.staff_name_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.staff_name_var, width=14).pack(side="left", padx=6)
        self.is_mgr_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(row, text="マネージャー", variable=self.is_mgr_var).pack(side="left", padx=6)
        self.restricted_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            row, text="制限(平日A/土曜Bのみ)", variable=self.restricted_var
        ).pack(side="left", padx=6)
        ttk.Button(row, text="追加/更新", command=self._upsert_staff).pack(side="left", padx=6)
        ttk.Button(row, text="削除", command=self._delete_staff).pack(side="left", padx=6)

        self.staff_list = tk.Listbox(box, height=6)
        self.staff_list.pack(fill="x", padx=8, pady=6)
        self.staff_list.bind("<<ListboxSelect>>", lambda _e: self._on_staff_select())

    def _build_calendar_panel(self, parent: ttk.Frame):
        box = ttk.Labelframe(parent, text="休業日(祝日等) と 希望休")
        box.pack(fill="both", expand=True, pady=6)

        top = ttk.Frame(box)
        top.pack(fill="x", padx=8, pady=6)
        ttk.Label(top, text="選択スタッフ").pack(side="left")
        self.sel_staff_var = tk.StringVar(value="(未選択)")
        ttk.Label(top, textvariable=self.sel_staff_var).pack(side="left", padx=8)
        self.auto_holiday_var = tk.BooleanVar(value=self.state.auto_close_jp_holidays)
        ttk.Checkbutton(
            top, text="祝日を自動休業にする", variable=self.auto_holiday_var, command=self._rebuild_calendar
        ).pack(side="left", padx=8)

        note = ttk.Label(
            box,
            text="日曜は自動で休業。祝日は自動休業(チェックでON/OFF)。臨時休業は「スタッフ未選択」で日付クリック。希望休はスタッフを選んで日付クリック。",
            wraplength=420,
        )
        note.pack(fill="x", padx=8)

        self.cal_frame = ttk.Frame(box)
        self.cal_frame.pack(fill="both", expand=True, padx=8, pady=6)
        self._rebuild_calendar()

    def _build_preview_panel(self, parent: ttk.Frame):
        box = ttk.Labelframe(parent, text="生成結果プレビュー")
        box.pack(fill="both", expand=True, pady=6)

        cols = ("date", "dow", "type") + tuple(SLOT_ORDER)
        self.preview = ttk.Treeview(box, columns=cols, show="headings", height=20)
        self.preview.heading("date", text="日付")
        self.preview.heading("dow", text="曜")
        self.preview.heading("type", text="種別")
        self.preview.column("date", width=100, anchor="center")
        self.preview.column("dow", width=40, anchor="center")
        self.preview.column("type", width=60, anchor="center")
        for s in SLOT_ORDER:
            self.preview.heading(s, text=SLOT_LABEL_JA[s])
            self.preview.column(s, width=110, anchor="center")

        ysb = ttk.Scrollbar(box, orient="vertical", command=self.preview.yview)
        xsb = ttk.Scrollbar(box, orient="horizontal", command=self.preview.xview)
        self.preview.configure(yscroll=ysb.set, xscroll=xsb.set)
        self.preview.grid(row=0, column=0, sticky="nsew", padx=8, pady=6)
        ysb.grid(row=0, column=1, sticky="ns", pady=6)
        xsb.grid(row=1, column=0, sticky="ew", padx=8)
        box.rowconfigure(0, weight=1)
        box.columnconfigure(0, weight=1)

        self._assignments = None

    def _rebuild_calendar(self):
        for w in self.cal_frame.winfo_children():
            w.destroy()

        self.state.month = self.month_var.get().strip()
        start, end = month_range(self.state.month)
        self.state.auto_close_jp_holidays = bool(self.auto_holiday_var.get()) if hasattr(self, "auto_holiday_var") else True
        self._jp_holidays = (
            jp_holidays_in_month(self.state.month) if self.state.auto_close_jp_holidays else {}
        )

        # Header row
        for i, w in enumerate(["月", "火", "水", "木", "金", "土", "日"]):
            ttk.Label(self.cal_frame, text=w).grid(row=0, column=i, padx=2, pady=2)

        # Align to Monday=0
        r = 1
        c = start.weekday()

        for d in iter_dates(start, end):
            btn = tk.Button(self.cal_frame, text=str(d.day), width=4)
            btn.grid(row=r, column=c, padx=2, pady=2)
            btn.configure(command=lambda dd=d: self._on_day_click(dd))
            self._style_day_button(btn, d)

            c += 1
            if c >= 7:
                c = 0
                r += 1

    def _style_day_button(self, btn: tk.Button, d: date):
        # Sunday is always closed (informational styling)
        if d.weekday() == 6:
            btn.configure(bg="#e5e7eb", fg="#6b7280")
            return

        # Japan holiday (auto close)
        if d in self._jp_holidays:
            btn.configure(bg="#ffe4e6", fg="#991b1b")
            return

        # Closed date (holiday etc.)
        if d in self.state.closed_dates:
            btn.configure(bg="#fee2e2")  # light red
            return

        # Requested off for selected staff
        sid = self._selected_staff_id()
        if sid and d in self.state.requests_off.get(sid, set()):
            btn.configure(bg="#dbeafe")  # light blue
            return

        # Saturday highlight
        if d.weekday() == 5:
            btn.configure(bg="#fef3c7")  # light amber
            return

        btn.configure(bg="SystemButtonFace")

    def _selected_staff_id(self) -> str | None:
        sel = self.staff_list.curselection()
        if not sel:
            return None
        line = self.staff_list.get(sel[0])
        # "S1 | Aさん | MGR"
        return line.split("|", 1)[0].strip()

    def _on_staff_select(self):
        sid = self._selected_staff_id()
        if not sid:
            self.sel_staff_var.set("(未選択)")
            self.staff_id_var.set("")
            self.staff_name_var.set("")
            self.is_mgr_var.set(False)
            self.restricted_var.set(False)
        else:
            s = next((x for x in self.state.staff if x.id == sid), None)
            self.sel_staff_var.set(f"{s.id} {s.name}" if s else sid)
            if s:
                self.staff_id_var.set(s.id)
                self.staff_name_var.set(s.name)
                self.is_mgr_var.set(bool(s.is_manager))
                self.restricted_var.set(bool(s.allowed_kinds))
        self._rebuild_calendar()

    def _on_day_click(self, d: date):
        if d.weekday() == 6:
            return  # Sundays are always closed

        # If no staff selected, toggle as closed date. If staff selected, toggle request off.
        sid = self._selected_staff_id()
        if sid is None:
            if d in self._jp_holidays:
                self.status_var.set(f"{d.isoformat()} は祝日のため自動休業です。")
                return
            if d in self.state.closed_dates:
                self.state.closed_dates.remove(d)
            else:
                self.state.closed_dates.add(d)
        else:
            sset = self.state.requests_off.setdefault(sid, set())
            if d in sset:
                sset.remove(d)
            else:
                sset.add(d)

        self._rebuild_calendar()

    def _upsert_staff(self):
        sid = self.staff_id_var.get().strip()
        name = self.staff_name_var.get().strip()
        if not sid or not name:
            messagebox.showerror("入力エラー", "ID と 名前 を入力してください。")
            return
        is_mgr = bool(self.is_mgr_var.get())
        restricted = bool(self.restricted_var.get())
        existing = next((i for i, s in enumerate(self.state.staff) if s.id == sid), None)
        allowed = (KIND_WD_A, KIND_SAT_B) if restricted else None
        s = Staff(id=sid, name=name, is_manager=is_mgr, allowed_kinds=allowed)
        if existing is None:
            self.state.staff.append(s)
        else:
            self.state.staff[existing] = s
        self._refresh_staff_list()

    def _delete_staff(self):
        sid = self._selected_staff_id()
        if not sid:
            return
        self.state.staff = [s for s in self.state.staff if s.id != sid]
        self.state.requests_off.pop(sid, None)
        self._refresh_staff_list()
        self._rebuild_calendar()

    def _refresh_staff_list(self):
        self.staff_list.delete(0, "end")
        for s in self.state.staff:
            tag = "MGR" if s.is_manager else "-"
            lim = "LIMIT" if s.allowed_kinds else "-"
            self.staff_list.insert("end", f"{s.id} | {s.name} | {tag} | {lim}")

    def _load_sample(self):
        path = "sample_config.json"
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except FileNotFoundError:
            messagebox.showerror("読込エラー", f"{path} が見つかりません。")
            return
        self._load_from_raw(raw)

    def _load_json(self):
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not path:
            return
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        self._load_from_raw(raw)

    def _load_template(self):
        path = filedialog.askopenfilename(filetypes=[("Excel", "*.xlsx")])
        if not path:
            return
        try:
            mi = import_from_template_xlsx(path)
        except Exception as e:
            messagebox.showerror("読込エラー", str(e))
            return
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
        }
        self._load_from_raw(raw)
        self.status_var.set("テンプレから読み込みました。")

    def _load_from_raw(self, raw: dict):
        self.month_var.set(str(raw.get("month", self.month_var.get())))
        self.state.month = self.month_var.get().strip()
        self.state.auto_close_jp_holidays = bool(raw.get("auto_close_jp_holidays", True))
        if hasattr(self, "auto_holiday_var"):
            self.auto_holiday_var.set(self.state.auto_close_jp_holidays)
        self.state.staff = [
            Staff(
                id=s["id"],
                name=s["name"],
                is_manager=bool(s.get("is_manager", False)),
                allowed_kinds=tuple(s["allowed_kinds"]) if s.get("allowed_kinds") else None,
            )
            for s in raw.get("staff", [])
        ]
        self.state.closed_dates = {_parse_date(d) for d in raw.get("closed_dates", [])}
        self.state.requests_off = {
            sid: {_parse_date(d) for d in ds} for sid, ds in raw.get("requests_off", {}).items()
        }
        self._refresh_staff_list()
        self._rebuild_calendar()
        self.status_var.set("読み込みました。")

    def _save_json(self):
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if not path:
            return
        raw = {
            "month": self.month_var.get().strip(),
            "auto_close_jp_holidays": bool(self.auto_holiday_var.get()) if hasattr(self, "auto_holiday_var") else True,
            "closed_dates": sorted(d.isoformat() for d in self.state.closed_dates),
            "staff": [
                {
                    "id": s.id,
                    "name": s.name,
                    "is_manager": s.is_manager,
                    "allowed_kinds": list(s.allowed_kinds) if s.allowed_kinds else None,
                }
                for s in self.state.staff
            ],
            "requests_off": {
                sid: sorted(d.isoformat() for d in ds) for sid, ds in self.state.requests_off.items()
            },
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(raw, f, ensure_ascii=False, indent=2)
        self.status_var.set("JSONを保存しました。")

    def _save_template(self):
        path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")])
        if not path:
            return
        try:
            mi = self._make_month_input()
        except Exception as e:
            messagebox.showerror("出力エラー", str(e))
            return
        export_template_xlsx(mi, path)
        self.status_var.set("テンプレを出力しました。")

    def _make_month_input(self) -> MonthInput:
        month = self.month_var.get().strip()
        if not month or len(month) != 7 or month[4] != "-":
            raise ValueError("対象月は YYYY-MM 形式で入力してください。")
        if len(self.state.staff) < 5:
            raise ValueError("スタッフは最低5人必要です。")
        reqs_off = {sid: tuple(sorted(ds)) for sid, ds in self.state.requests_off.items()}
        return MonthInput(
            month=month,
            staff=tuple(self.state.staff),
            closed_dates=tuple(sorted(self.state.closed_dates)),
            requests_off=reqs_off,
            requirements=self.state.requirements,
            auto_close_jp_holidays=bool(self.auto_holiday_var.get()) if hasattr(self, "auto_holiday_var") else True,
        )

    def _generate(self):
        try:
            mi = self._make_month_input()
            res = solve(mi)
        except (ValueError, SolveError) as e:
            messagebox.showerror("生成エラー", str(e))
            return

        self._assignments = res.assignments
        self.preview.delete(*self.preview.get_children())
        staff_by_id = mi.staff_by_id()
        for a in res.assignments:
            d = a.day
            kind = "土曜" if d.weekday() == 5 else "平日"
            self.preview.insert(
                "",
                "end",
                values=(
                    d.isoformat(),
                    _weekday_jp(d),
                    kind,
                    *[
                        (staff_by_id[sid].name if (sid := a.slots.get(slot_name)) else "")
                        for slot_name in SLOT_ORDER
                    ],
                ),
            )
        self.status_var.set(f"生成完了: {len(res.assignments)}日")

    def _export(self):
        if not self._assignments:
            messagebox.showerror("出力エラー", "先に「生成」を実行してください。")
            return
        path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")])
        if not path:
            return
        mi = self._make_month_input()
        export_xlsx(mi, self._assignments, path)
        self.status_var.set("Excelに出力しました。")


def run_app():
    app = App()
    app.mainloop()
