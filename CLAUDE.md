# shiftgen — Claude Code 向けプロジェクトガイド

## プロジェクト概要

月次シフト表を自動生成する Python デスクトップアプリ。
GUI (tkinter) と CLI の両エントリポイントを持ち、Google OR-Tools の CP-SAT ソルバーで制約最適化を行い、openpyxl で Excel ファイルを出力する。

## 環境

- Python 3.12
- 仮想環境: `.venv/`（macOS では `source .venv/bin/activate` で有効化）
- 依存パッケージ: `pip install -r requirements.txt`
- 開発用追加: `pip install -r requirements-dev.txt`（PyInstaller を含む）

## 実行方法

```bash
# GUI 起動
python app.py

# CLI 実行（JSON → Excel）
python -m shiftgen.cli --in sample_config.json --out output.xlsx

# CLI 実行（Excelテンプレ → Excel）
python -m shiftgen.cli --in template.xlsx --out output.xlsx
```

## ディレクトリ構成

```
shiftgen/
├── app.py                  # GUI エントリポイント（tkinter App クラスを起動）
├── cli.py                  # CLI エントリポイント（shiftgen.cli へ委譲）
├── staff_master.json       # 固定スタッフマスタ（GUI の「スタッフ読込」で参照）
├── sample_config.json      # 入力 JSON サンプル
├── requirements.txt        # 本番依存
├── requirements-dev.txt    # 開発依存（PyInstaller）
└── shiftgen/
    ├── domain.py           # データモデル（Staff, MonthInput, Assignment, スロット定数）
    ├── solver.py           # CP-SAT ソルバー（solve 関数）
    ├── gui.py              # tkinter GUI（App クラス）
    ├── cli.py              # CLI（argparse）
    ├── excel.py            # シフト表 Excel 出力
    ├── template_excel.py   # テンプレート Excel の入出力
    ├── io.py               # JSON 入力パース
    ├── calendar_utils.py   # 日付ユーティリティ
    ├── jp_holidays.py      # 日本祝日取得（jpholiday）
    └── app_paths.py        # 実行パス解決（PyInstaller 対応）
```

## ドメイン知識

### シフトスロット

| 種別 (kind) | スロット名 | 表示名 | 任意枠 |
|---|---|---|---|
| wd_early | wd_early | 平日早番 | 必須 |
| wd_a | wd_a1 | 平日A(1) | 必須 |
| wd_a | wd_a2 | 平日A(2) | **任意** |
| wd_b | wd_b1 | 平日B(1) | 必須 |
| wd_b | wd_b2 | 平日B(2) | 必須 |
| wd_bplus | wd_bplus | 平日B+ | 必須 |
| sat_early | sat_early | 土曜早番 | 必須 |
| sat_a | sat_a1 | 土曜A(1) | 必須 |
| sat_a | sat_a2 | 土曜A(2) | 必須 |
| sat_a | sat_a3 | 土曜A(3) | **任意** |
| sat_b | sat_b1 | 土曜B(1) | 必須 |
| sat_b | sat_b2 | 土曜B(2) | 必須 |

### 制約ロジック（solver.py）

- 各スロットに 1 人のスタッフを割り当て
- 1 人のスタッフは 1 日 1 スロットのみ
- **マネージャーが毎営業日最低 1 人**出勤（`is_manager=True`）
- 土曜出勤は 1 人あたり `saturday_max_per_person`（デフォルト 3）回まで
- 希望休 (`requests_off`) と種別制限 (`allowed_kinds`) はハード制約
- 厳格制約で解なし → **制約緩和モード** (`relaxed=True`) で再挑戦し `is_partial=True` を返す
- 最適化目標: 勤務日数の均等化（`max_total - min_total` 最小化）＋任意枠の最大充填

### 入力 JSON スキーマ（sample_config.json 参照）

```json
{
  "month": "YYYY-MM",
  "auto_close_jp_holidays": true,
  "closed_dates": ["YYYY-MM-DD"],
  "staff": [
    {"id": "S1", "name": "名前", "is_manager": true},
    {"id": "S8", "name": "名前", "is_manager": false, "allowed_kinds": ["wd_a", "sat_b"]}
  ],
  "requests_off": {"S1": ["YYYY-MM-DD"]},
  "requirements": {"saturday_max_per_person": 3, "prefer_max_headcount": true}
}
```

### staff_master.json

スタッフリストを固定管理するファイル。`{"staff": [...]}` 形式。
GUI 起動時に自動検索し、なければファイル選択ダイアログを表示する。

## コーディング規約

- `from __future__ import annotations` を各ファイル先頭に記載（Python 3.12 互換）
- データモデルは `@dataclass(frozen=True)` で不変オブジェクトとして定義
- ソルバー内部は OR-Tools の `cp_model` を直接使用（抽象化レイヤーなし）
- GUI 側のスレッド安全性: ソルバーは別スレッドで実行し `self.after(0, ...)` で UI 更新
- エラーは `SolveError` (RuntimeError サブクラス) に集約して GUI/CLI 両方で捕捉
- 日本語文字列はソースコード内に直書き（`ensure_ascii=False` で JSON 出力）

## テスト

現時点でテストコードは未整備。変更後は以下で動作確認する:

```bash
python -m shiftgen.cli --in sample_config.json --out /tmp/test_output.xlsx
python app.py
```

## パッケージング（PyInstaller）

```bash
pyinstaller app.py --name shiftgen --onefile --windowed
```

Windows 向け exe では `staff_master.json` を実行ファイルと同じディレクトリに置く必要がある（`app_paths.py` の `app_base_dir()` 参照）。
