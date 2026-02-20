# shiftgen (シフト表自動作成)

1ヶ月分のシフト表を自動作成し、Excel (`.xlsx`) に出力するデスクトップアプリの最小実装です (Windows想定)。

## できること (現状)

- 対象: 1ヶ月 (YYYY-MM)
- 休業日: 日曜日 + 日本の祝日 (自動) + 任意の臨時休業日 (手入力)
- 平日シフト: 平日早番(1) / 平日A(1-2) / 平日B(2) / 平日B+(1)
- 土曜シフト: 土曜早番(1) / 土曜A(2-3) / 土曜B(2)
- マネージャースキル保有者が1日あたり最低1人必要 (シフト種別は不問)
- 希望休 (手入力) を必ず守る
- 同一個人の土曜勤務は月3回まで
- 雇用形態による制限: 「平日A」と「土曜B」しか入れないスタッフを設定可能
- できるだけ勤務日数が公平になるように自動割当
- 生成したシフトをExcelに出力

## セットアップ (Windows想定)

1. Python 3.11+ をインストール
2. このフォルダで以下を実行

```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
```

Pythonを入れられないPC向けの `exe` 化は `/Users/iwasakimasaki/Documents/New project/BUILD_WINDOWS_EXE.md` を参照してください。

## 使い方

### 1) デスクトップUIで作成 (推奨)

```bash
python app.py
```

- `staff_master.json` を編集しておくと、GUIの「スタッフ読込」ボタンで毎回の手入力を省略できます。
- 対象月、スタッフ、マネージャー該当者、休業日(祝日)、希望休を入力
- 「生成」してプレビュー
- 「Excel出力」で `.xlsx` 保存

### 2) JSONから作成 (CI/自動化向け)

```bash
python -m shiftgen.cli --in sample_config.json --out out.xlsx
```

### 3) Excelテンプレから作成 (運用向け)

GUIの「テンプレ出力」でテンプレを作り、`RequestsOffCalendar` シートでスタッフ別カレンダー形式で希望休を追記してから「テンプレ読込」で読み込めます。

（互換用として、従来の `RequestsOff` シート 1行=1希望休 形式も読み込み対応しています。）

CLIでも可能です:

```bash
python -m shiftgen.cli --in requests.xlsx --out out.xlsx
```

## 画面表示とは？

このアプリでは、生成前に以下を画面で確認できます。

- 月間カレンダーで「希望休」「臨時休業日」をクリック入力 (日曜は自動休業、祝日は自動休業のON/OFFあり)
- 生成結果の一覧表 (日付ごとに、平日/土曜の各シフト枠の割当が見える)
