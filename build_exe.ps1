# PowerShell script to build a single-file executable using pyinstaller
param(
    [string]$entry = "src/app.py",
    [string]$name = "stock_screener"
)

pyinstaller --onefile --name $name $entry

Write-Host "Build finished. Check the dist\$name executable.";