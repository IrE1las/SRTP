param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
try {
    & (Join-Path $PSScriptRoot '启动项目.ps1') -NoBrowser:$NoBrowser
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} catch {
    Write-Host ('Startup failed: ' + $_.Exception.Message) -ForegroundColor Red
    exit 1
}
