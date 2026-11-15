# Script PowerShell chay pipeline nap kho du lieu olist_dw
# Su dung bien moi truong tu file .env neu co, hoac gia tri mac dinh

$envFile = Join-Path $PSScriptRoot ".env"
$dbHost = "localhost"
$dbPort = "5433"
$dbName = "olist_dw"
$dbUser = "postgres"
$dbPass = ""

if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match "^\s*([^#=]+)\s*=\s*(.*)$") {
            $key = $matches[1].Trim()
            $val = $matches[2].Trim()
            if ($key -eq "DB_HOST") { $dbHost = $val }
            if ($key -eq "DB_PORT") { $dbPort = $val }
            if ($key -eq "DB_NAME") { $dbName = $val }
            if ($key -eq "DB_USER") { $dbUser = $val }
            if ($key -eq "DB_PASSWORD") { $dbPass = $val }
        }
    }
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " Chay ETL Pipeline cho database: $dbName ($dbHost:$dbPort)" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# Kiem tra Python
if (Get-Command python -ErrorAction SilentlyContinue) {
    Write-Host "[1/2] Khoi chay ETL Pipeline bang Python (nhanh nhat)..." -ForegroundColor Yellow
    python "$PSScriptRoot\etl_pipeline.py"
} else {
    Write-Host "[!] Khong tim thay Python. Vui long chay: python etl_pipeline.py" -ForegroundColor Red
}
