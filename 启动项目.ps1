param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$runtimeDir = Join-Path $projectRoot '.runtime'
$backendDir = Join-Path $projectRoot 'framework\backend'
$frontendDir = Join-Path $projectRoot 'framework\frontend'
$pythonExe = Join-Path $runtimeDir 'venv\Scripts\python.exe'
$nodeExe = (Get-Command node.exe -ErrorAction Stop).Source
if (-not (Test-Path -LiteralPath $pythonExe)) { throw 'Project Python environment is missing.' }
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
    $process = Start-Process -FilePath $Executable -ArgumentList $Arguments -WorkingDirectory $Directory -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtimeDir "$Name.log") -RedirectStandardError (Join-Path $runtimeDir "$Name.error.log")
    return $process.Id
}
$backendPid = Start-ProjectService 8000 $pythonExe '-m uvicorn main:app --host 127.0.0.1 --port 8000' $backendDir 'backend'
$vitePath = Join-Path $frontendDir 'node_modules\vite\bin\vite.js'
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
if (-not $NoBrowser) {
    $edgeExe = 'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
    if(-not (Test-Path -LiteralPath $edgeExe)){throw 'Microsoft Edge was not found.'}
    $profile = Join-Path $runtimeDir 'browser-profile'
    Start-Process -FilePath $edgeExe -ArgumentList ('--user-data-dir="' + $profile + '" --no-first-run --new-window http://127.0.0.1:5173/admin')
}
Write-Output 'SRTP ready: http://127.0.0.1:5173/'
