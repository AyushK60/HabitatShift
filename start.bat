@echo off
setlocal EnableExtensions
rem ============================================================
rem  HabitatShift one-click startup (double-click me).
rem
rem  - checks the existing .venv and backend dependencies
rem  - builds frontend/dist if it is missing (needs Node.js)
rem  - picks a free localhost port (prefers 8098, then +1..+200)
rem  - starts the backend hidden, waits until it responds, then
rem    opens HabitatShift in the default browser
rem  - never starts a duplicate session if one is already running
rem
rem  Runtime records and logs live in .runtime (git-ignored).
rem  Stop the session with stop.bat.
rem
rem  Internal flag: "start.bat --nopause" skips the end-of-run
rem  pause/timeout (used by automated tests).
rem ============================================================
set "HABITAT_BAT=%~f0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$m = '#' + 'PS_BEGIN'; $raw = Get-Content -Raw -LiteralPath '%~f0'; $i = $raw.IndexOf($m); if ($i -lt 0) { Write-Host 'start.bat is corrupted: PS marker missing.'; exit 1 }; Invoke-Expression $raw.Substring($i + $m.Length)"
set "HABITAT_EXIT=%ERRORLEVEL%"
if %HABITAT_EXIT% NEQ 0 (
  if /i not "%~1"=="--nopause" pause
) else (
  if /i not "%~1"=="--nopause" timeout /t 4 /nobreak >nul
)
exit /b %HABITAT_EXIT%

#PS_BEGIN
$ErrorActionPreference = 'Stop'
try {
  $root    = Split-Path -Parent $env:HABITAT_BAT
  $runtime = Join-Path $root '.runtime'
  $venvPy  = Join-Path $root '.venv\Scripts\python.exe'
  $pidFile  = Join-Path $runtime 'server.pid'
  $portFile = Join-Path $runtime 'server.port'
  $urlFile  = Join-Path $runtime 'server.url'
  $logFile  = Join-Path $runtime 'server.log'
  $preferredPort = 8098

  Write-Host '================================================='
  Write-Host ' HabitatShift - one-click startup'
  Write-Host '================================================='

  New-Item -ItemType Directory -Force -Path $runtime | Out-Null

  function Test-PortFree([int]$Port) {
    $listener = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Loopback, $Port)
    try { $listener.Start(); $listener.Stop(); return $true } catch { return $false }
  }
  function Test-ServerUp([int]$Port) {
    try {
      Invoke-WebRequest -UseBasicParsing -Uri ('http://127.0.0.1:{0}/' -f $Port) -TimeoutSec 2 | Out-Null
      return $true
    } catch {
      if ($_.Exception.Response) { return $true }
      return $false
    }
  }

  # ---- already running? --------------------------------------
  if (Test-Path $pidFile) {
    $oldPid = Get-Content $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1
    $oldProc = $null
    if ($oldPid -match '^\d+$') {
      $oldProc = Get-CimInstance Win32_Process -Filter ('ProcessId = {0}' -f $oldPid) -ErrorAction SilentlyContinue
    }
    if ($oldProc -and $oldProc.CommandLine -and
        ($oldProc.CommandLine.IndexOf('uvicorn', [System.StringComparison]::OrdinalIgnoreCase) -ge 0)) {
      $oldPort = $preferredPort
      if (Test-Path $portFile) {
        $recorded = Get-Content $portFile | Select-Object -First 1
        if ($recorded -match '^\d+$') { $oldPort = [int]$recorded }
      }
      $url = 'http://127.0.0.1:{0}/' -f $oldPort
      Write-Host ('HabitatShift is already running (pid {0}) at {1}' -f $oldPid, $url)
      Write-Host 'Opening the existing session instead of starting a duplicate.'
      Start-Process $url | Out-Null
      exit 0
    }
    Remove-Item $pidFile, $portFile, $urlFile -ErrorAction SilentlyContinue
    Write-Host 'Removed stale runtime records from a previous session.'
  }

  # ---- python virtual environment ----------------------------
  if (-not (Test-Path $venvPy)) {
    Write-Host 'ERROR: the Python virtual environment was not found:'
    Write-Host ('  {0}' -f $venvPy)
    Write-Host 'Create it first, e.g.:'
    Write-Host '  py -3.11 -m venv .venv'
    Write-Host '  .venv\Scripts\pip install -r backend\requirements.txt'
    exit 1
  }

  # ---- backend dependencies ----------------------------------
  cmd /c ('"{0}" -c "import uvicorn, fastapi" > nul 2>&1' -f $venvPy)
  if ($LASTEXITCODE -ne 0) {
    Write-Host 'Backend dependencies missing - installing backend\requirements.txt ...'
    $pipLog = Join-Path $runtime 'pip-install.log'
    cmd /c ('"{0}" -m pip install --disable-pip-version-check -r "{1}" > "{2}" 2>&1' -f $venvPy, (Join-Path $root 'backend\requirements.txt'), $pipLog)
    cmd /c ('"{0}" -c "import uvicorn, fastapi" > nul 2>&1' -f $venvPy)
    if ($LASTEXITCODE -ne 0) {
      Write-Host 'ERROR: backend dependencies could not be installed. See .runtime\pip-install.log'
      exit 1
    }
  }
  Write-Host 'Backend dependencies: OK'

  # ---- frontend build ----------------------------------------
  $distIndex = Join-Path $root 'frontend\dist\index.html'
  if (-not (Test-Path $distIndex)) {
    $npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if (-not $npm) {
      Write-Host 'ERROR: frontend\dist is missing and npm was not found on PATH.'
      Write-Host 'Build the frontend manually:  cd frontend && npm install && npm run build'
      exit 1
    }
    if (-not (Test-Path (Join-Path $root 'frontend\node_modules'))) {
      Write-Host 'Installing frontend dependencies (npm install) ...'
      Push-Location (Join-Path $root 'frontend')
      cmd /c ('npm install --no-audit --no-fund > "{0}" 2>&1' -f (Join-Path $runtime 'npm-install.log'))
      Pop-Location
    }
    Write-Host 'Building the frontend (npm run build, this can take a minute) ...'
    Push-Location (Join-Path $root 'frontend')
    $buildLog = Join-Path $runtime 'npm-build.log'
    cmd /c ('npm run build > "{0}" 2>&1' -f $buildLog)
    Pop-Location
    if (-not (Test-Path $distIndex)) {
      Write-Host 'ERROR: the frontend build failed. See .runtime\npm-build.log'
      Get-Content $buildLog -Tail 10 -ErrorAction SilentlyContinue | ForEach-Object { Write-Host ('  {0}' -f $_) }
      exit 1
    }
    Write-Host 'Frontend build: OK'
  } else {
    Write-Host 'Frontend build: OK (frontend\dist present)'
  }

  # ---- port selection ----------------------------------------
  $port = 0
  if (Test-PortFree $preferredPort) {
    $port = $preferredPort
  } else {
    Write-Host ('Port {0} is in use - searching for a free port ...' -f $preferredPort)
    for ($candidate = $preferredPort + 1; $candidate -le $preferredPort + 200; $candidate++) {
      if (Test-PortFree $candidate) { $port = $candidate; break }
    }
  }
  if ($port -eq 0) {
    Write-Host 'ERROR: no free port found between 8098 and 8298.'
    exit 1
  }

  # ---- launch -------------------------------------------------
  Write-Host ('Starting the HabitatShift backend on port {0} ...' -f $port)
  $inner = '"{0}" -m uvicorn backend.app.api.app:app --host 127.0.0.1 --port {1} > "{2}" 2>&1' -f $venvPy, $port, $logFile
  Start-Process -FilePath $env:ComSpec -ArgumentList ('/d /s /c "{0}"' -f $inner) -WindowStyle Hidden | Out-Null

  # ---- wait until the server responds -------------------------
  $ready = $false
  for ($attempt = 0; $attempt -lt 90; $attempt++) {
    Start-Sleep -Seconds 1
    if (Test-ServerUp $port) { $ready = $true; break }
  }
  if (-not $ready) {
    Write-Host 'ERROR: the backend did not respond within 90 seconds. Last log lines:'
    Get-Content $logFile -Tail 15 -ErrorAction SilentlyContinue | ForEach-Object { Write-Host ('  {0}' -f $_) }
    exit 1
  }

  # ---- record runtime info ------------------------------------
  # The cmd wrapper's PID is not the server PID. Primary method:
  # match this project's uvicorn python process by command line
  # (works even where the TCP connection table is not visible).
  $serverPid = $null
  $portArg = '--port {0}' -f $port
  $ourServer = Get-CimInstance Win32_Process -Filter "Name LIKE 'python%'" -ErrorAction SilentlyContinue |
    Where-Object {
      $_.CommandLine -and
      ($_.CommandLine.IndexOf($root, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) -and
      ($_.CommandLine.IndexOf('uvicorn', [System.StringComparison]::OrdinalIgnoreCase) -ge 0) -and
      ($_.CommandLine.IndexOf($portArg, [System.StringComparison]::OrdinalIgnoreCase) -ge 0)
    } | Select-Object -First 1
  if ($ourServer) { $serverPid = $ourServer.ProcessId }
  if (-not $serverPid) {
    try {
      $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
      if ($conn) { $serverPid = $conn.OwningProcess }
    } catch { }
  }
  if (-not $serverPid) {
    $netstatLine = netstat -ano | Select-String (':{0} .*LISTENING' -f $port) | Select-Object -First 1
    if ($netstatLine) { $serverPid = ($netstatLine.ToString().Trim() -split '\s+')[-1] }
  }

  $url = 'http://127.0.0.1:{0}/' -f $port
  Set-Content -Path $pidFile  -Value $serverPid -Encoding ascii
  Set-Content -Path $portFile -Value $port      -Encoding ascii
  Set-Content -Path $urlFile  -Value $url       -Encoding ascii

  Write-Host ''
  Write-Host '================================================='
  Write-Host ('  HabitatShift is running:  {0}' -f $url)
  Write-Host ('  backend pid: {0}' -f $serverPid)
  Write-Host '  stop it with stop.bat'
  Write-Host '================================================='
  Start-Process $url | Out-Null
  exit 0
} catch {
  Write-Host ('ERROR: {0}' -f $_.Exception.Message)
  exit 1
}
