param(
    [switch]$NoBrowser,
    [switch]$PrepareOnly,
    [ValidateRange(1024, 65435)][int]$BackendPort = 8000,
    [ValidateRange(1024, 65435)][int]$FrontendPort = 5173
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$root = $PSScriptRoot
$runtime = Join-Path $root '.runtime'
$guard = $null
$transcribing = $false
$created = @()
$exitCode = 0

function Show-Project([int]$WebPort, [int]$ApiPort) {
    Write-Host "SRTP ready: http://127.0.0.1:$WebPort/"
    Write-Host "Admin: http://127.0.0.1:$WebPort/admin   Account: admin / 00000000 (fresh database)"
    Write-Host "API docs: http://127.0.0.1:$ApiPort/docs"
    if (-not $NoBrowser) { Start-Process "http://127.0.0.1:$WebPort/admin" }
}

try {
    # A parent shell can pass a module path from PowerShell 7; include Windows modules explicitly.
    $env:PSModulePath = (Join-Path $PSHOME 'Modules') + ';' + (Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\Modules')
    Import-Module Microsoft.PowerShell.Utility -ErrorAction Stop
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    if (-not [Environment]::Is64BitOperatingSystem -or $env:PROCESSOR_ARCHITECTURE -eq 'ARM64' -or $env:PROCESSOR_ARCHITEW6432 -eq 'ARM64') {
        throw 'This launcher supports Windows 10/11 x64. Other architectures need a separate runtime manifest.'
    }
    if ([Environment]::OSVersion.Version.Major -lt 10) { throw 'Windows 10 or newer is required.' }
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    New-Item -ItemType Directory -Path (Join-Path $runtime 'tmp') -Force | Out-Null
    try { $guard = [IO.File]::Open((Join-Path $runtime 'launch-v2.lock'), 'OpenOrCreate', 'ReadWrite', 'None') }
    catch { throw 'Another startup/shutdown is in progress for this checkout. Wait for it to finish.' }
    Start-Transcript -LiteralPath (Join-Path $runtime 'launch-v2.log') -Append | Out-Null
    $transcribing = $true
    . (Join-Path $root 'scripts\bootstrap.ps1')
    . (Join-Path $root 'scripts\services.ps1')
    $env:TEMP = Join-Path $runtime 'tmp'
    $env:TMP = $env:TEMP
    $env:PYTHONDONTWRITEBYTECODE = '1'
    $env:PYTHONUTF8 = '1'
    $env:PYTHONIOENCODING = 'utf-8'
    $env:PYTHONHOME = $null
    $env:PYTHONPATH = $null
    $env:NODE_OPTIONS = $null
    $env:DATABASE_URL = 'sqlite:///' + (Join-Path $root 'framework\backend\railway.db').Replace('\', '/')
    $recordPath = Join-Path $runtime 'services-v2.json'
    $fingerprint = Get-TextHash ($root + ((@('runtime-manifest.json', 'launch.ps1', 'scripts\bootstrap.ps1', 'scripts\backend_entry.py', 'scripts\spawn_service.py', 'scripts\services.ps1', 'framework\backend\main.py', 'framework\backend\requirements.lock.txt', 'framework\frontend\package-lock.json', 'framework\frontend\package.json', 'framework\frontend\vite.config.js') | ForEach-Object { (Get-FileHash -LiteralPath (Join-Path $root $_)).Hash }) -join ':'))
    if (Test-Path -LiteralPath $recordPath) {
        $old = Get-Content -LiteralPath $recordPath -Raw | ConvertFrom-Json
        if ($old.root -eq $root) {
            $api = @($old.services | Where-Object name -eq 'backend')
            $web = @($old.services | Where-Object name -eq 'frontend')
            if (-not $PrepareOnly -and $old.fingerprint -eq $fingerprint -and $api.Count -eq 1 -and $web.Count -eq 1 -and
                (Test-ServiceReady $api[0] "http://127.0.0.1:$($api[0].port)/api/health") -and
                (Test-ServiceReady $web[0] "http://127.0.0.1:$($web[0].port)/api/health")) {
                Show-Project $web[0].port $api[0].port
                exit 0
            }
            foreach ($service in $old.services) { Stop-OwnedService $service }
        }
    }
    $executables = Initialize-ProjectRuntime $root
    Write-Utf8 (Join-Path $runtime 'environment-v2.json') ($executables | ConvertTo-Json)
    if ($PrepareOnly) { Write-Host 'Project environment ready.'; exit 0 }

    $BackendPort = Get-FreePort $BackendPort
    $FrontendPort = Get-FreePort $FrontendPort
    if ($BackendPort -eq $FrontendPort) { $FrontendPort = Get-FreePort ($FrontendPort + 1) }
    $env:SRTP_BACKEND_URL = "http://127.0.0.1:$BackendPort"
    $record = [ordered]@{ schema = 2; root = $root; fingerprint = $fingerprint; services = @() }
    $specs = @(
        @{ name = 'backend'; port = $BackendPort; exe = $executables.python; marker = (Join-Path $root 'scripts\backend_entry.py'); dir = (Join-Path $root 'framework\backend') },
        @{ name = 'frontend'; port = $FrontendPort; exe = $executables.node; marker = (Join-Path $root 'framework\frontend\node_modules\vite\bin\vite.js'); dir = (Join-Path $root 'framework\frontend') }
    )
    foreach ($spec in $specs) {
        [string[]]$serviceArguments = if ($spec.name -eq 'backend') { @([string]$spec.port) }
            else { @('--host', '127.0.0.1', '--port', [string]$spec.port, '--strictPort') }
        $processIdText = & $executables.python (Join-Path $root 'scripts\spawn_service.py') $spec.exe $spec.marker $spec.dir (Join-Path $runtime ($spec.name + '-v2.log')) (Join-Path $runtime ($spec.name + '-v2.error.log')) @serviceArguments
        if ($LASTEXITCODE -ne 0) { throw "Could not create $($spec.name)." }
        $startedProcessId = [int]$processIdText
        $info = Get-ServiceProcess $startedProcessId
        if (-not $info) { throw "$($spec.name) exited immediately. Inspect .runtime service logs." }
        $service = [ordered]@{ name = $spec.name; port = $spec.port; marker = $spec.marker; processes = @(New-ProcessRecord $info) }
        $created += $service
        $record.services = $created
        Write-Utf8 $recordPath ($record | ConvertTo-Json -Depth 8)
        $ready = $false
        for ($attempt = 0; $attempt -lt 60; $attempt++) {
            $listener = Get-PortListener $spec.port
            if ($listener) {
                $listenerInfo = Get-ServiceProcess $listener.OwningProcess
                if ($listenerInfo -and $listenerInfo.CommandLine -and $listenerInfo.CommandLine.IndexOf($spec.marker, [StringComparison]::OrdinalIgnoreCase) -ge 0 -and
                    ($listenerInfo.ProcessId -eq $startedProcessId -or $listenerInfo.ParentProcessId -eq $startedProcessId)) {
                    if ($listenerInfo.ProcessId -ne $startedProcessId -and @($service.processes | Where-Object pid -eq $listenerInfo.ProcessId).Count -eq 0) {
                        $service.processes += New-ProcessRecord $listenerInfo
                        Write-Utf8 $recordPath ($record | ConvertTo-Json -Depth 8)
                    }
                    if (Test-ServiceReady $service "http://127.0.0.1:$($spec.port)/api/health") { $ready = $true; break }
                } else { throw "Port $($spec.port) was taken by another process during startup. Retry; no unrelated process was stopped." }
            }
            if (-not (Get-ServiceProcess $startedProcessId)) { break }
            Start-Sleep -Milliseconds 500
        }
        if (-not $ready) { throw "$($spec.name) did not become ready. Inspect .runtime\$($spec.name)-v2.error.log." }
    }
    Write-Host '[setup] Checking local teaching data ...'
    & $executables.python (Join-Path $root 'framework\backend\scripts\seed_local_data.py') | Out-Host
    if ($LASTEXITCODE -ne 0) { throw 'Teaching data initialization failed. Inspect launch-v2.log.' }
    Show-Project $FrontendPort $BackendPort
} catch {
    foreach ($service in $created) { Stop-OwnedService $service }
    Write-Host "[startup failed] $($_.Exception.Message)" -ForegroundColor Red
    Write-Host $_.ScriptStackTrace
    Write-Host "Log folder: $runtime"
    $exitCode = 1
} finally {
    if ($transcribing) { Stop-Transcript | Out-Null }
    if ($guard) { $guard.Dispose() }
}
exit $exitCode
