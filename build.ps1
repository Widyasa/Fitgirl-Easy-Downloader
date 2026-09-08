$ErrorActionPreference = "Stop"

python -m pip install -r requirements-build.txt
python -m PyInstaller --clean --noconfirm FitgirlDownloader.spec

Write-Host "Built: dist\FitgirlEasyDownloader.exe"
