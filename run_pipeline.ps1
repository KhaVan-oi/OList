# Script PowerShell chay pipeline nap kho du lieu
# Doc cau hinh tu .env (DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD)

$envFile = Join-Path $PSScriptRoot ".env"
$dbHost = "localhost"
$dbPort = "5435"
$dbName = "olist_dw"
$dbUser = "postgres"
$dbPass = ""

function Strip-Quotes([string]$val) {
    $v = $val.Trim()
    if ($v.Length -ge 2) {
        $q = $v.Substring(0, 1)
        if (($q -eq "'" -or $q -eq '"') -and $v.EndsWith($q)) {
            return $v.Substring(1, $v.Length - 2)
        }
    }
    return $v
}

if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match "^\s*([^#=]+)\s*=\s*(.*)$") {
            $key = $matches[1].Trim()
            $val = Strip-Quotes $matches[2]
            if ($key -eq "DB_HOST") { $dbHost = $val }
            if ($key -eq "DB_PORT") { $dbPort = $val }
            if ($key -eq "DB_NAME") { $dbName = $val }
            if ($key -eq "DB_USER") { $dbUser = $val }
            if ($key -eq "DB_PASSWORD") { $dbPass = $val }
        }
    }
}

# Truyen sang process Python (db_connect.py cung doc .env)
$env:DB_HOST = $dbHost
$env:DB_PORT = $dbPort
$env:DB_NAME = $dbName
$env:DB_USER = $dbUser
$env:DB_PASSWORD = $dbPass

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " Chay ETL Pipeline cho database: $dbName ($dbHost:$dbPort)" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

if (Get-Command python -ErrorAction SilentlyContinue) {
    Write-Host "[1/2] Khoi chay ETL Pipeline bang Python..." -ForegroundColor Yellow
    python "$PSScriptRoot\etl_pipeline.py"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[!] Pipeline that bai (exit $LASTEXITCODE)" -ForegroundColor Red
        exit $LASTEXITCODE
    }
} else {
    Write-Host "[!] Khong tim thay Python. Vui long chay: python etl_pipeline.py" -ForegroundColor Red
    exit 1
}
