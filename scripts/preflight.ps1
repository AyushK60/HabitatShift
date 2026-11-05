# HabitatShift M0 — environment preflight
# Records tool versions so the development log is auditable.
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Show-Item($label, $value) { "{0,-22} {1}" -f $label, $value }

Write-Output "HabitatShift M0 preflight"
Write-Output ("timestamp_utc".PadRight(22) + (Get-Date).ToUniversalTime().ToString('o'))
Show-Item 'cwd' (Get-Location).Path
Write-Output "--- runtimes ---"
Show-Item 'python' ((& python --version 2>&1) -join ' ')
Show-Item 'py_launcher' ((& py -0p 2>&1) -join ' ')
Show-Item 'pip' ((& pip --version 2>&1) -join ' ')
Show-Item 'node' ((& node --version 2>&1) -join ' ')
Show-Item 'npm' ((& npm --version 2>&1) -join ' ')
Show-Item 'git' ((& git --version 2>&1) -join ' ')
Show-Item 'venv_python' ((& "$root\.venv\Scripts\python.exe" --version 2>&1) -join ' ')
Write-Output "--- geospatial stack in venv ---"
& "$root\.venv\Scripts\python.exe" -c "import rasterio,numpy,pyproj,shapely,pystac_client,fastapi;print('rasterio',rasterio.__version__);print('gdal',rasterio.__gdal_version__);print('numpy',numpy.__version__);print('pyproj',pyproj.__version__);print('shapely',shapely.__version__)"
Write-Output "--- system ---"
Show-Item 'os' ((Get-CimInstance Win32_OperatingSystem).Caption)
Show-Item 'ram_gb' ([math]::Round((Get-CimInstance Win32_OperatingSystem).TotalVisibleMemorySize/1MB,1))
Show-Item 'gpu' (((Get-CimInstance Win32_VideoController).Name) -join '; ')
Show-Item 'free_disk_gb' ([math]::Round((Get-PSDrive ($root.Substring(0,1))).Free/1GB,1))
Write-Output "--- connectivity ---"
try {
  $r = Invoke-WebRequest 'https://earth-search.aws.element84.com/v1' -TimeoutSec 20 -UseBasicParsing
  Show-Item 'earth_search' "HTTP $($r.StatusCode)"
} catch { Show-Item 'earth_search' "FAILED $($_.Exception.Message)" }
Write-Output "--- repo state ---"
Show-Item 'tracked_files' ((& git ls-files | Measure-Object).Count)
Show-Item 'working_tree' (((& git status --porcelain) | Measure-Object).Count)
