$ErrorActionPreference = 'Stop'
$env:PSModulePath = (Join-Path $PSHOME 'Modules') + ';' + (Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\Modules')
. (Join-Path $PSScriptRoot 'scripts\services.ps1')
$runtime = Join-Path $PSScriptRoot '.runtime'
$recordFile = Join-Path $runtime 'services-v2.json'
$lockPath = Join-Path $runtime 'launch-v2.lock'
$guard = $null
try {
    if (-not (Test-Path -LiteralPath $recordFile)) { Write-Host 'No v2 services saved for this checkout.'; exit 0 }
    try { $guard = [IO.File]::Open($lockPath, 'OpenOrCreate', 'ReadWrite', 'None') }
    catch { throw 'Startup or shutdown is already running. Wait for it to finish.' }
    $record = Get-Content -LiteralPath $recordFile -Raw | ConvertFrom-Json
    if ($record.root -ne $PSScriptRoot) { throw 'Service record belongs to a different directory. No processes were stopped.' }
    foreach ($service in $record.services) { Stop-OwnedService $service }
    Write-Host 'Stopped services owned by this checkout. Other checkouts are unaffected.'
} catch { Write-Host "[stop failed] $($_.Exception.Message)" -ForegroundColor Red; exit 1 }
finally { if ($guard) { $guard.Dispose() } }
