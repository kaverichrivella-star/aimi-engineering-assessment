# PowerShell script to build a single-file Streamlit executable using PyInstaller.
param(
    [string]$entry = "launcher.py",
    [string]$name = "stock_screener"
)

python -m PyInstaller --clean --noconfirm --onefile --name $name `
    --collect-all streamlit `
    --collect-all yfinance `
    --add-data "src;src" `
    --add-data "symbols.csv;." `
    --add-data "models;models" `
    $entry

Write-Host "Build finished. Check the dist\$name executable.";