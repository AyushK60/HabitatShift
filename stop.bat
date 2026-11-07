@echo off
setlocal EnableExtensions
rem ============================================================
rem  HabitatShift one-click shutdown (double-click me).
rem
rem  Stops ONLY the backend session started by start.bat:
rem  - reads the PID recorded in .runtime\server.pid and kills it
rem    only after verifying its command line is this project's
rem    uvicorn backend (path under this project + uvicorn +
rem    backend.app.api.app).
rem  - falls back to a command-line scan restricted to python
rem    processes launched from THIS project's .venv.
rem  - releases the recorded port and removes the .runtime
rem    records (pid, port, url, log).
rem  Unrelated Python processes and applications are never
rem  terminated. No administrator privileges are required.
rem ============================================================
set "HABITAT_BAT=%~f0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$m = '#' + 'PS_BEGIN'; $raw = Get-Content -Raw -LiteralPath '%~f0'; $i = $raw.IndexOf($m); if ($i -lt 0) { Write-Host 'stop.bat is corrupted: PS marker missing.'; exit 1 }; Invoke-Expression $raw.Substring($i + $m.Length)"
set "HABITAT_EXIT=%ERRORLEVEL%"
if %HABITAT_EXIT% NEQ 0 (
  if /i not "%~1"=="--nopause" pause
)
exit /b %HABITAT_EXIT%

#PS_BEGIN
$ErrorActionPreference = 'Continue'
try {
  $root    = Split-Path -Parent $env:HABITAT_BAT
  $runtime = Join-Path $root '.runtime'
  $pidFile  = Join-Path $runtime 'server.pid'
  $portFile = Join-Path $runtime 'server.port'
  $urlFile  = Join-Path $runtime 'server.url'
  $logFile  = Join-Path $runtime 'server.log'

  Write-Host '================================================='
  Write-Host ' HabitatShift - stopping the local application'
  Write-Host '================================================='

  # A process counts as our backend only if its command line
  # contains uvicorn, the exact app target and THIS project's
  # path (i.e. the python.exe of this project's own .venv).
  function Test-IsOurBackend($Proc, [string]$RootPath) {
    if (-not $Proc) { return $false }
    $cmdLine = $Proc.CommandLine
    if (-not $cmdLine) { return $false }
    if ($cmdLine.IndexOf('uvicorn', [System.StringComparison]::OrdinalIgnoreCase) -lt 0) { return $false }
    if ($cmdLine.IndexOf('backend.app.api.app', [System.StringComparison]::OrdinalIgnoreCase) -lt 0) { return $false }
    if ($cmdLine.IndexOf($RootPath, [System.StringComparison]::OrdinalIgnoreCase) -lt 0) { return $false }
    return $true
  }

  $targets = @()

  if (Test-Path $pidFile) {
    $recordedPid = Get-Content $pidFile | Select-Object -First 1
    if ($recordedPid -match '^\d+$') {
      $proc = Get-CimInstance Win32_Process -Filter ('ProcessId = {0}' -f $recordedPid) -ErrorAction SilentlyContinue
      if (Test-IsOurBackend $proc $root) {
        $targets += $proc
      } else {
        Write-Host 'The recorded session is no longer running (stale record).'
      }
    }
  }

  if ($targets.Count -eq 0) {
    # Fallback: find this project's uvicorn backend by command line,
    # restricted to the recorded port when one is known, so only the
    # exact session started by start.bat is stopped.
    $portArg = $null
    if (Test-Path $portFile) {
      $recordedPort = Get-Content $portFile | Select-Object -First 1
      if ($recordedPort -match '^\d+$') { $portArg = '--port {0}' -f $recordedPort }
    }
    $candidates = Get-CimInstance Win32_Process -Filter "Name LIKE 'python%'" -ErrorAction SilentlyContinue |
      Where-Object {
        (Test-IsOurBackend $_ $root) -and
        ((-not $portArg) -or ($_.CommandLine.IndexOf($portArg, [System.StringComparison]::OrdinalIgnoreCase) -ge 0))
      }
    if ($candidates) { $targets = @($candidates) }
  }

  if ($targets.Count -eq 0) {
    Write-Host 'No HabitatShift session was found. Nothing to stop.'
    Remove-Item $pidFile, $portFile, $urlFile, $logFile -ErrorAction SilentlyContinue
    exit 0
  }

  foreach ($target in $targets) {
    Write-Host ('Stopping the HabitatShift backend (pid {0}) ...' -f $target.ProcessId)
    Stop-Process -Id $target.ProcessId -Force -ErrorAction SilentlyContinue
  }
  foreach ($target in $targets) {
    for ($wait = 0; $wait -lt 40; $wait++) {
      if (-not (Get-Process -Id $target.ProcessId -ErrorAction SilentlyContinue)) { break }
      Start-Sleep -Milliseconds 250
    }
    if (Get-Process -Id $target.ProcessId -ErrorAction SilentlyContinue) {
      Write-Host ('WARNING: pid {0} did not exit.' -f $target.ProcessId)
    }
  }

  # ---- port release check and runtime cleanup -----------------
  $recordedPort = $null
  if (Test-Path $portFile) { $recordedPort = Get-Content $portFile | Select-Object -First 1 }
  Remove-Item $pidFile, $portFile, $urlFile, $logFile -ErrorAction SilentlyContinue
  Write-Host 'Runtime records removed from .runtime.'

  if ($recordedPort -match '^\d+$') {
    Start-Sleep -Milliseconds 500
    $stillListening = Get-NetTCPConnection -LocalPort ([int]$recordedPort) -State Listen -ErrorAction SilentlyContinue
    if ($stillListening) {
      Write-Host ('NOTE: port {0} is still listening (pid {1}) - that listener is not ours and was left untouched.' -f $recordedPort, $stillListening[0].OwningProcess)
    } else {
      Write-Host ('Port {0} released.' -f $recordedPort)
    }
  }

  Write-Host 'HabitatShift stopped.'
  exit 0
} catch {
  Write-Host ('ERROR: {0}' -f $_.Exception.Message)
  exit 1
}
