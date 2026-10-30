param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false) } catch {}
$env:PYTHONIOENCODING = 'utf-8'
# A launcher can inherit PowerShell 7's module path. Prefer this engine's
# own system modules so Windows PowerShell 5.1 can resolve its standard commands.
$nativeModuleRoot = Join-Path $PSHOME 'Modules'
if (Test-Path -LiteralPath $nativeModuleRoot) {
    $env:PSModulePath = $nativeModuleRoot + [System.IO.Path]::PathSeparator + $env:PSModulePath
}

Write-Host 'SRTP startup is running. Please keep this window open.'
Write-Host '[1/5] Checking the project environment ...'
try {
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$runtimeDir = Join-Path $projectRoot '.runtime'
$backendDir = Join-Path $projectRoot 'framework\backend'
$frontendDir = Join-Path $projectRoot 'framework\frontend'
$pythonExe = Join-Path $runtimeDir 'venv\Scripts\python.exe'
if (Test-Path -LiteralPath (Join-Path $runtimeDir 'startup-repair\upgrade-in-progress.lock')) { throw 'Database upgrade is in progress. Wait for it to finish before starting again.' }

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
$envText = Get-Content -LiteralPath $envFile -Raw -Encoding UTF8
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

Write-Host '[2/5] Checking the current database before starting services ...'
& $pythonExe (Join-Path $backendDir 'scripts\check_startup.py') --database (Join-Path $backendDir 'railway.db')
if ($LASTEXITCODE -ne 0) { throw 'Database preflight failed. See the specific reason above; no migration was applied by the launcher.' }

function Wait-ProjectService($Name, $ServiceId, $Url) {
    $watch = [System.Diagnostics.Stopwatch]::StartNew()
    $lastProgress = -5
    while ($watch.Elapsed.TotalSeconds -lt 30) {
        if (-not (Get-Process -Id $ServiceId -ErrorAction SilentlyContinue)) {
            $errorLog = Join-Path $runtimeDir "$Name.error.log"
            if (Test-Path -LiteralPath $errorLog) {
                Write-Host "[$Name] Process exited. Latest error log:" -ForegroundColor Red
                Get-Content -LiteralPath $errorLog -Encoding UTF8 -Tail 16 | ForEach-Object { Write-Host $_ }
            }
            throw "$Name exited before it was ready. Check .runtime\$Name.error.log."
        }
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -eq 200) {
                if ($Name -eq 'backend') {
                    $health = $response.Content | ConvertFrom-Json
                    if ($health.status -ne 'ok' -or $health.service -ne 'railway-interlocking-api' -or $health.stage -ne 'S6') {
                        Write-Host '[backend] The responding service is not the current S6 application.' -ForegroundColor Red
                        throw 'Unexpected backend health version.'
                    }
                }
                # Do not accept another process response after our process has exited.
                if (Get-Process -Id $ServiceId -ErrorAction SilentlyContinue) {
                    Write-Host "[$Name] Ready: $Url"
                    return
                }
            }
        } catch {}
        if ($watch.Elapsed.TotalSeconds - $lastProgress -ge 3) {
            Write-Host ("[$Name] Waiting for response ... {0}s" -f [int]$watch.Elapsed.TotalSeconds)
            $lastProgress = $watch.Elapsed.TotalSeconds
        }
        Start-Sleep -Milliseconds 500
    }
    throw "$Name did not become ready in 30 seconds. Check .runtime\$Name.error.log."
}

function Start-ProjectService($Port, $Executable, $Arguments, $Directory, $Name) {
    Write-Host ("[launch] Starting/checking {0} on port {1} ..." -f $Name, $Port)
    # Some Windows networking providers omit a live listener from CIM. Reuse
    # an owned saved process before trying to start another copy on its port.
    $recordPath = Join-Path $runtimeDir 'services.json'
    if (Test-Path -LiteralPath $recordPath) {
        $savedServices = Get-Content -LiteralPath $recordPath -Raw | ConvertFrom-Json
        [int]$savedId = 0
        if ([int]::TryParse([string]$savedServices.$Name, [ref]$savedId) -and $savedId -gt 0) {
            $savedProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $savedId"
            $ownedCommand = if ($Name -eq 'backend') {
                $savedProcess.CommandLine -like '*uvicorn main:app*'
            } else {
                $savedProcess.CommandLine -like "*$projectRoot*" -and $savedProcess.CommandLine -like '*vite.js*'
            }
            if ($savedProcess -and $savedProcess.ExecutablePath -eq $Executable -and $ownedCommand) {
                return $savedId
            }
        }
    }
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
    $process = Start-Process -FilePath $Executable -ArgumentList $Arguments -WorkingDirectory $Directory -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtimeDir "$Name.log") -RedirectStandardError (Join-Path $runtimeDir "$Name.error.log")
    return $process.Id
}
Write-Host '[3/5] Starting backend ...'
$backendPid = Start-ProjectService 8000 $pythonExe '-m uvicorn main:app --host 127.0.0.1 --port 8000' $backendDir 'backend'
Wait-ProjectService 'backend' $backendPid 'http://127.0.0.1:8000/api/health'
Write-Host '[4/5] Starting frontend ...'
$frontendPid = Start-ProjectService 5173 $nodeExe ('"' + $vitePath + '" --host 127.0.0.1 --port 5173 --strictPort') $frontendDir 'frontend'
@{backend=$backendPid;frontend=$frontendPid} | ConvertTo-Json | Set-Content (Join-Path $runtimeDir 'services.json')
Wait-ProjectService 'frontend' $frontendPid 'http://127.0.0.1:5173/'

# First run on a fresh database: import the reviewed shunting table and lab topics.
Write-Host '[5/5] Checking local teaching data (skipped when already present) ...'
& $pythonExe (Join-Path $backendDir 'scripts\seed_local_data.py')
if ($LASTEXITCODE -ne 0) { throw 'Local data bootstrap failed. Inspect .runtime logs.' }

if (-not $NoBrowser) {
    Write-Host '[launch] Opening the project page in your browser ...'
    $edgeCandidates = @(
        'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
        'C:\Program Files\Microsoft\Edge\Application\msedge.exe'
    )
    $edgeExe = $edgeCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if ($edgeExe) {
        $profile = Join-Path $runtimeDir 'browser-profile'
        Start-Process -FilePath $edgeExe -ArgumentList ('--user-data-dir="' + $profile + '" --no-first-run --new-window http://127.0.0.1:5173/admin')
    } else {
        Write-Host 'Edge was not found; opening the default browser instead.'
        Start-Process 'http://127.0.0.1:5173/admin'
    }
}
Write-Host ''
Write-Host 'SRTP started. Open in your browser:'
Write-Host '  Web page:  http://127.0.0.1:5173/'
Write-Host '  Admin:     http://127.0.0.1:5173/admin'
Write-Host '  API docs:  http://127.0.0.1:8000/docs'
Write-Host '  Account:   admin / 00000000'
Write-Host ''

} catch {
    Write-Host ''
    Write-Host ('Startup failed: ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Logs: ' + (Join-Path $PSScriptRoot '.runtime'))
    exit 1
}
