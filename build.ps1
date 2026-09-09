$ErrorActionPreference = "Stop"

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Python 3.13 virtual environment not found. Run: py -3.13 -m venv .venv"
}

& $python -m pip install -r requirements-build.txt
& $python -m PyInstaller --clean --noconfirm FitgirlDownloader.spec

Write-Host "Built: dist\FitgirlEasyDownloader.exe"
