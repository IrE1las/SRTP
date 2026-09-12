param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$runtimeDir = Join-Path $projectRoot '.runtime'
$backendDir = Join-Path $projectRoot 'framework\backend'
$frontendDir = Join-Path $projectRoot 'framework\frontend'
$pythonExe = Join-Path $runtimeDir 'venv\Scripts\python.exe'

function Test-PythonBase([string[]]$base) {
    try {
        $null = & @base -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,12) else 1)' 2>$null
        return ($LASTEXITCODE -eq 0)
    } catch { return $false }
}

# Locate Python 3.12+: prefer python.exe on PATH, then versions from the py launcher.
if (-not (Test-Path -LiteralPath $pythonExe)) {
    $pythonBase = @()
    $py = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($py -and (Test-PythonBase @($py.Source))) { $pythonBase = @($py.Source) }
    if ($pythonBase.Count -eq 0) {
        $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
        if ($launcher) {
            foreach ($ver in @('-3.12','-3.13','-3.14','-3')) {
                if (Test-PythonBase @($launcher.Source, $ver)) { $pythonBase = @($launcher.Source, $ver); break }
            }
        }
    }
    if ($pythonBase.Count -eq 0) { throw 'Python 3.12 or newer was not found. Install it from https://www.python.org/downloads/ and try again.' }
    Write-Host '[launch] First run: creating project virtual environment .runtime\venv ...'
    New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null
    & @pythonBase -m venv (Join-Path $runtimeDir 'venv')
    if (-not (Test-Path -LiteralPath $pythonExe)) { throw 'Virtual environment creation failed.' }
}

# Backend dependencies are (re)installed when the lock file changes.
$lockFile = Join-Path $backendDir 'requirements.lock.txt'
$lockHash = (Get-FileHash -Algorithm SHA256 $lockFile).Hash
$depMarker = Join-Path $runtimeDir 'requirements.sha256'
if (-not (Test-Path -LiteralPath $depMarker) -or ((Get-Content -LiteralPath $depMarker -Raw).Trim() -ne $lockHash)) {
    Write-Host '[launch] Installing backend dependencies (first run or lock file updated) ...'
    & $pythonExe -m pip install --disable-pip-version-check -r $lockFile
    if ($LASTEXITCODE -ne 0) { throw 'Backend dependency installation failed. Check your network and try again.' }
    $lockHash | Set-Content -LiteralPath $depMarker -Encoding ascii
}

# Local .env: copy from the template on first run and generate a machine-local SECRET_KEY.
$envFile = Join-Path $backendDir '.env'
if (-not (Test-Path -LiteralPath $envFile)) {
    Write-Host '[launch] First run: creating local .env from template ...'
    Copy-Item -LiteralPath (Join-Path $backendDir '.env.example') -Destination $envFile
}
$envText = Get-Content -LiteralPath $envFile -Raw
if ($envText -notmatch '(?m)^SECRET_KEY=\S+$' -or $envText -match 'SECRET_KEY=replace-with-a-new-random-secret-before-running') {
    $random = -join ((1..64) | ForEach-Object { '{0:x}' -f (Get-Random -Maximum 16) })
    if ($envText -match '(?m)^SECRET_KEY=') {
        $envText = [regex]::Replace($envText, '(?m)^SECRET_KEY=.*$', "SECRET_KEY=$random")
    } else {
        $envText = $envText.TrimEnd() + "`r`nSECRET_KEY=$random`r`n"
    }
    [System.IO.File]::WriteAllText($envFile, $envText, (New-Object System.Text.UTF8Encoding($false)))
    Write-Host '[launch] Generated a machine-local random SECRET_KEY.'
}

# Frontend dependencies: run npm ci when node_modules is missing.
$nodeExe = (Get-Command node.exe -ErrorAction Stop).Source
$vitePath = Join-Path $frontendDir 'node_modules\vite\bin\vite.js'
if (-not (Test-Path -LiteralPath $vitePath)) {
    Write-Host '[launch] First run: installing frontend dependencies (npm ci) ...'
    $npmExe = (Get-Command npm.cmd -ErrorAction Stop).Source
    & $npmExe --prefix $frontendDir ci
    if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed. Check your network and try again.' }
}

New-Item -ItemType Directory -Path (Join-Path $runtimeDir 'tmp') -Force | Out-Null
$env:TEMP = Join-Path $runtimeDir 'tmp'
$env:TMP = $env:TEMP
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:DATABASE_URL = 'sqlite:///' + (Join-Path $backendDir 'railway.db').Replace('\','/')

function Start-ProjectService($Port, $Executable, $Arguments, $Directory, $Name) {
    $listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($listener) {
        $processInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $($listener.OwningProcess)"
        # Windows venv uses a launcher which may spawn the base Python interpreter.
        if ($Name -eq 'backend' -and $processInfo.CommandLine -like '*uvicorn main:app*') {
            $parentInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $($processInfo.ParentProcessId)"
            if ($parentInfo.ExecutablePath -eq $Executable -and $parentInfo.CommandLine -like '*uvicorn main:app*') {
                return $parentInfo.ProcessId
            }
        }
        if ($processInfo.ExecutablePath -ne $Executable -or ($Name -eq 'frontend' -and $processInfo.CommandLine -notlike "*$projectRoot*")) {
            throw "Port $Port is used by another process; it was not stopped."
        }
        return $listener.OwningProcess
    }
    $process = Start-Process -FilePath $Executable -ArgumentList $Arguments -WorkingDirectory $Directory -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtimeDir "$Name.log") -RedirectStandardError (Join-Path $runtimeDir "$Name.error.log")
    return $process.Id
}
$backendPid = Start-ProjectService 8000 $pythonExe '-m uvicorn main:app --host 127.0.0.1 --port 8000' $backendDir 'backend'
$frontendPid = Start-ProjectService 5173 $nodeExe ('"' + $vitePath + '" --host 127.0.0.1 --port 5173 --strictPort') $frontendDir 'frontend'
@{backend=$backendPid;frontend=$frontendPid} | ConvertTo-Json | Set-Content (Join-Path $runtimeDir 'services.json')
foreach ($url in @('http://127.0.0.1:8000/api/health','http://127.0.0.1:5173/')) {
    $ready = $false
    for ($attempt=0; $attempt -lt 30; $attempt++) {
        try { $response=Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2; if($response.StatusCode -eq 200){$ready=$true;break} } catch {}
        Start-Sleep -Milliseconds 500
    }
    if(-not $ready){throw "Service did not become ready: $url. Inspect .runtime logs."}
}

# First run on a fresh database: import the reviewed shunting table and lab topics.
Write-Host '[launch] Checking local teaching data (skipped when already present) ...'
& $pythonExe (Join-Path $backendDir 'scripts\seed_local_data.py')
if ($LASTEXITCODE -ne 0) { throw 'Local data bootstrap failed. Inspect .runtime logs.' }

if (-not $NoBrowser) {
    $edgeExe = 'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
    if(-not (Test-Path -LiteralPath $edgeExe)){throw 'Microsoft Edge was not found.'}
    $profile = Join-Path $runtimeDir 'browser-profile'
    Start-Process -FilePath $edgeExe -ArgumentList ('--user-data-dir="' + $profile + '" --no-first-run --new-window http://127.0.0.1:5173/admin')
}
Write-Host ''
Write-Host 'SRTP started. Open in your browser:'
Write-Host '  Web page:  http://127.0.0.1:5173/'
Write-Host '  Admin:     http://127.0.0.1:5173/admin'
Write-Host '  API docs:  http://127.0.0.1:8000/docs'
Write-Host '  Account:   admin / 00000000'
Write-Host ''
