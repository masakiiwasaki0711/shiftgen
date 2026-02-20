from __future__ import annotations

import argparse

from excel import export_xlsx
from io import load_month_input_json
from solver import solve
from template_excel import import_from_template_xlsx


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", required=True, help="input JSON or template xlsx path")
    ap.add_argument("--out", dest="out_path", required=True, help="output xlsx path")
    args = ap.parse_args(argv)

    if args.in_path.lower().endswith(".xlsx"):
        mi = import_from_template_xlsx(args.in_path)
    else:
        mi = load_month_input_json(args.in_path)
    res = solve(mi)
    export_xlsx(mi, res.assignments, args.out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
