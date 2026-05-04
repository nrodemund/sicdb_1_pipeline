@echo off
setlocal

REM Creates or updates src.zip from src\sicdb_1_pipeline.
REM Run this file from the repository root.

set "SOURCE_DIR=src\sicdb_1_pipeline"
set "ZIP_FILE=src.zip"

if not exist "%SOURCE_DIR%\" (
    echo ERROR: Source directory not found: %SOURCE_DIR%
    exit /b 1
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference = 'Stop';" ^
  "$source = Join-Path (Get-Location) '%SOURCE_DIR%';" ^
  "$zip = Join-Path (Get-Location) '%ZIP_FILE%';" ^
  "if (Test-Path $zip) { Remove-Item $zip -Force };" ^
  "Compress-Archive -Path (Join-Path $source '*') -DestinationPath $zip -Force;" ^
  "Write-Host ('Created/updated: ' + $zip)"

if errorlevel 1 (
    echo ERROR: Failed to create/update %ZIP_FILE%.
    exit /b 1
)

echo Done.
exit /b 0
