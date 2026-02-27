from __future__ import annotations


def main() -> int:
    from shiftgen.cli import main as shiftgen_main
    return shiftgen_main()


if __name__ == "__main__":
    raise SystemExit(main())
