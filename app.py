from __future__ import annotations

import traceback


def _show_fatal_error(title: str, body: str) -> None:
    # Avoid importing tkinter at module import time; keep it local so CLI use stays clean.
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(title, body)
        root.destroy()
    except Exception:
        # Last resort: print to stderr.
        print(title)
        print(body)


def main() -> int:
    try:
        from gui import run_app

        run_app()
        return 0
    except Exception:
        tb = traceback.format_exc()
        _show_fatal_error("shiftgen エラー", tb)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
