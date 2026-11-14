$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$record = Join-Path $projectRoot '.runtime\services.json'
if (-not (Test-Path -LiteralPath $record)) { Write-Output 'No saved services.'; exit }
$services = Get-Content -LiteralPath $record -Raw | ConvertFrom-Json
foreach ($name in @('backend','frontend')) {
    $serviceId = $services.$name
    $info = Get-CimInstance Win32_Process -Filter "ProcessId = $serviceId"
    if (-not $info) { continue }
    $owned = if ($name -eq 'backend') {
        $info.ExecutablePath -eq (Join-Path $projectRoot '.runtime\venv\Scripts\python.exe') -and $info.CommandLine -like '*uvicorn main:app*'
    } else {
        $info.CommandLine -like "*$projectRoot*" -and $info.CommandLine -like '*vite.js*'
    }
    if (-not $owned) { throw "Saved process $serviceId no longer belongs to this project." }
    if ($name -eq 'backend') {
        $children = Get-CimInstance Win32_Process -Filter "ParentProcessId = $serviceId"
        foreach($child in $children) {
            if($child.CommandLine -like '*uvicorn main:app*'){ Stop-Process -Id $child.ProcessId }
        }
    }
    if(Get-Process -Id $serviceId -ErrorAction SilentlyContinue){Stop-Process -Id $serviceId}
    Write-Output "Stopped $name ($serviceId)"
}
