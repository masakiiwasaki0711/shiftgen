# shiftgen (シフト表自動作成)

1ヶ月分のシフト表を自動作成し、Excel (`.xlsx`) に出力するデスクトップアプリです。
macOS・Windows で動作します。

## できること

- 対象: 1ヶ月 (YYYY-MM)
- 休業日: 日曜日 + 日本の祝日 (自動) + 任意の臨時休業日 (クリック入力)
- 平日シフト: 平日早番(1) / 平日A(1-2) / 平日B(2) / 平日B+(1)
- 土曜シフト: 土曜早番(1) / 土曜A(2-3) / 土曜B(2)
- マネージャースキル保有者が1日あたり最低1人必要 (シフト種別は不問)
- 希望休 (クリック入力) を必ず守る
- 同一個人の土曜勤務は月3回まで
- 雇用形態による制限: 「平日A」と「土曜B」しか入れないスタッフを設定可能
- できるだけ勤務日数が公平になるように自動割当
- 制約を満たす解がない場合、土曜上限・マネージャー配置を自動緩和して再挑戦（制約緩和モード）
- 生成したシフトをExcelに出力

## セットアップ

### macOS

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### Windows

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 使い方

### 1) デスクトップUIで作成 (推奨)

**macOS:** `run.command` をダブルクリック

ターミナルから実行する場合:
```bash
.venv/bin/python3 app.py
```

> **注意:** `python3 app.py` を直接実行すると、仮想環境外の Python が使われ `ortools` が見つからないエラーになります。必ず `.venv` 内の Python を使ってください。

**Windows:**
```powershell
.venv\Scripts\python app.py
```

- `staff_master.json` を編集しておくと、GUIの「スタッフ読込」ボタンで毎回の手入力を省略できます
- 対象月・スタッフ・マネージャー該当者・休業日・希望休を入力
- 「生成」してプレビュー確認
- 「Excel出力」で `.xlsx` 保存

### 2) JSONから作成 (CLI・自動化向け)

```bash
python -m shiftgen.cli --in sample_config.json --out out.xlsx
```

`sample_config.json` を参考に入力ファイルを作成してください。

### 3) Excelテンプレから作成 (運用向け)

GUIの「テンプレ出力」でテンプレを作成し、`RequestsOffCalendar` シートでスタッフ別カレンダー形式に希望休を入力してから「テンプレ読込」で読み込めます。

CLIでも使用できます:

```bash
python -m shiftgen.cli --in requests.xlsx --out out.xlsx
```

## カスタマイズ

### 勤務時間単価の変更

1日あたりの勤務時間は `shiftgen/excel.py` の先頭にある定数で管理しています。

```python
# shiftgen/excel.py
HOURS_WEEKDAY = 8.5   # 平日1回あたりの勤務時間 (h)
HOURS_SATURDAY = 4.5  # 土曜1回あたりの勤務時間 (h)
```

この値を変更するだけで、Excel出力の「勤務時間集計」シートとGUIのサマリー表示の両方に反映されます。

## exe化 (Windows配布用)

Python を入れられない共有PCへの配布方法は `BUILD_WINDOWS_EXE.md` を参照してください。

> **注意:** `staff_master.json` は exe に同梱されません。「スタッフ読込」を自動化したい場合は、`staff_master.json` を exe と同じフォルダに配置してください。
>
> ```
> dist/
>   shiftgen.exe
>   staff_master.json   ← ここに置く
> ```
