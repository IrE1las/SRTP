# Shared process ownership checks. Never trust a PID without creation time and path.
function Get-ServiceProcess([int]$ProcessId) {
    if ($ProcessId -le 0) { return $null }
    return Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction SilentlyContinue
}

function New-ProcessRecord($Info) {
    return [ordered]@{
        pid = [int]$Info.ProcessId
        created = $Info.CreationDate.ToUniversalTime().ToString('o')
        executable = $Info.ExecutablePath
    }
}

function Test-OwnedProcess($Record, [string]$Marker) {
    $info = Get-ServiceProcess ([int]$Record.pid)
    return ($null -ne $info -and $info.ExecutablePath -eq $Record.executable -and
        $info.CreationDate.ToUniversalTime().ToString('o') -eq $Record.created -and
        $info.CommandLine -and $info.CommandLine.IndexOf($Marker, [StringComparison]::OrdinalIgnoreCase) -ge 0)
}

function Get-PortListener([int]$Port) {
    return Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue | Select-Object -First 1
}

function Get-FreePort([int]$Preferred) {
    for ($candidate = $Preferred; $candidate -lt [Math]::Min($Preferred + 100, 65536); $candidate++) {
        $probe = New-Object Net.Sockets.TcpListener([Net.IPAddress]::Loopback, $candidate)
        try { $probe.Start(); return $candidate } catch {} finally { $probe.Stop() }
    }
    throw "No free local port near $Preferred."
}

function Stop-OwnedService($Service) {
    # Include a venv launcher's child, even if the launcher failed before recording it.
    $records = @($Service.processes)
    foreach ($record in @($Service.processes)) {
        if (Test-OwnedProcess $record $Service.marker) {
            $children = @(Get-CimInstance Win32_Process -Filter "ParentProcessId = $($record.pid)" -ErrorAction SilentlyContinue)
            foreach ($child in $children) {
                if ($child.CommandLine -and $child.CommandLine.IndexOf($Service.marker, [StringComparison]::OrdinalIgnoreCase) -ge 0) {
                    $records += New-ProcessRecord $child
                }
            }
        }
    }
    [array]::Reverse($records)
    foreach ($record in $records) {
        if (Test-OwnedProcess $record $Service.marker) {
            Stop-Process -Id $record.pid -ErrorAction SilentlyContinue
        }
    }
}

function Test-ServiceReady($Service, [string]$Url) {
    $listener = Get-PortListener $Service.port
    if (-not $listener) { return $false }
    $owned = @($Service.processes | Where-Object { $_.pid -eq $listener.OwningProcess -and (Test-OwnedProcess $_ $Service.marker) })
    if ($owned.Count -eq 0) { return $false }
    try { return (Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200 } catch { return $false }
}
