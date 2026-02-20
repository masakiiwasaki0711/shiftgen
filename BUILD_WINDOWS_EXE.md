# Windows exe化 (PyInstaller)

職場の共有PCにPythonを入れられない場合は、Windows上で `exe` を作って配布します。

## 前提

- Windows 10/11
- Python 3.11+ (exe作成用のPCにだけあればOK)

## 手順

PowerShellでこのリポジトリに移動してから:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
pyinstaller --noconfirm --clean shiftgen.spec
```

生成物:

- `dist\shiftgen.exe`

## メモ

- 生成されない場合は、`app.py` が例外をダイアログ表示するので内容を教えてください。
- 共有PCに配布するのは `dist\shiftgen.exe` だけでOKです。
