# HabitatShift M0 — run the proof viewer API
# Binds to localhost only; no external deployment.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$port = if ($env:HABITATSHIFT_PORT) { $env:HABITATSHIFT_PORT } else { '8091' }

if (-not (Test-Path "$root\.venv\Scripts\python.exe")) {
  throw "venv missing. Run: py -3.11 -m venv .venv; .\.venv\Scripts\pip install -r backend\requirements.txt"
}
if (-not (Test-Path "$root\data\manifests\m0_primary_study.json")) {
  Write-Warning "No manifest yet. Run: .\.venv\Scripts\python.exe scripts\build_primary_study.py"
}

Write-Output "HabitatShift proof viewer -> http://127.0.0.1:$port/"
& "$root\.venv\Scripts\python.exe" -m uvicorn backend.app.api.app:app --host 127.0.0.1 --port $port
