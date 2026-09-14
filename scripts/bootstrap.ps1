function Write-Utf8([string]$Path, [string]$Value) {
    [IO.File]::WriteAllText($Path, $Value, (New-Object Text.UTF8Encoding($false)))
}

function Get-TextHash([string]$Value) {
    $hasher = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($hasher.ComputeHash([Text.Encoding]::UTF8.GetBytes($Value)))).Replace('-', '').ToLowerInvariant() }
    finally { $hasher.Dispose() }
}

function Test-Stamp([string]$Path, [string]$Expected) {
    return ((Test-Path -LiteralPath $Path) -and (Get-Content -LiteralPath $Path -Raw).Trim() -eq $Expected)
}

function Save-VerifiedDownload([string]$Url, [string]$Destination, [string]$Hash) {
    if ((Test-Path -LiteralPath $Destination) -and (Get-FileHash -LiteralPath $Destination -Algorithm SHA256).Hash -eq $Hash) { return }
    if ($env:SRTP_OFFLINE -eq '1') { throw "Offline cache is missing: $Destination. Run once with network access." }
    $partial = $Destination + '.partial'
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        try {
            Write-Host "[download $attempt/3] $Url"
            # Windows PowerShell 5.1 treats [] in Invoke-WebRequest -OutFile as a wildcard.
            $request = [Net.WebRequest]::Create($Url)
            $request.Timeout = 300000
            $request.ReadWriteTimeout = 300000
            $response = $request.GetResponse()
            try {
                $stream = [IO.File]::Create($partial)
                try { $response.GetResponseStream().CopyTo($stream) } finally { $stream.Dispose() }
            } finally { $response.Dispose() }
            if ((Get-FileHash -LiteralPath $partial -Algorithm SHA256).Hash -ne $Hash) { throw 'SHA256 verification failed.' }
            Move-Item -LiteralPath $partial -Destination $Destination -Force
            return
        } catch {
            if ($attempt -eq 3) { throw "Download failed: $Url. Check your network/proxy and retry. $($_.Exception.Message)" }
            Start-Sleep -Seconds 2
        }
    }
}

function Save-BrokenRuntime([string]$Path, [string]$RuntimeRoot) {
    $absolute = [IO.Path]::GetFullPath($Path)
    $boundary = [IO.Path]::GetFullPath($RuntimeRoot).TrimEnd('\') + '\'
    if (-not $absolute.StartsWith($boundary, [StringComparison]::OrdinalIgnoreCase)) { throw 'Recovery path is outside .runtime.' }
    if (Test-Path -LiteralPath $absolute) {
        $backup = $absolute + '.previous-' + [guid]::NewGuid().ToString('N')
        Move-Item -LiteralPath $absolute -Destination $backup
        Write-Host "[repair] Previous runtime retained: $backup"
    }
}

function Initialize-ProjectRuntime([string]$Root) {
    $runtime = Join-Path $Root '.runtime'
    $toolsDir = Join-Path $runtime 'bootstrap-v2'
    $manifestPath = Join-Path $Root 'runtime-manifest.json'
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    $backend = Join-Path $Root 'framework\backend'
    $frontend = Join-Path $Root 'framework\frontend'
    New-Item -ItemType Directory -Path $toolsDir -Force | Out-Null
    $uvDir = Join-Path $toolsDir ('uv-' + $manifest.uv.version)
    $uvExe = Join-Path $uvDir 'uv.exe'
    $uvZip = Join-Path $toolsDir ('uv-' + $manifest.uv.version + '.zip')
    if (-not (Test-Path -LiteralPath $uvExe)) {
        Save-VerifiedDownload $manifest.uv.url $uvZip $manifest.uv.sha256
        $staging = Join-Path $toolsDir ('extract-' + [guid]::NewGuid().ToString('N'))
        [IO.Compression.ZipFile]::ExtractToDirectory($uvZip, $staging)
        Save-BrokenRuntime $uvDir $runtime
        Move-Item -LiteralPath $staging -Destination $uvDir
    }
    $uvVersion = & $uvExe --version
    if ($LASTEXITCODE -ne 0 -or $uvVersion -notlike ('uv ' + $manifest.uv.version + '*')) { throw "Invalid uv executable: $uvExe" }

    $env:UV_CACHE_DIR = Join-Path $toolsDir 'uv-cache'
    $env:UV_PYTHON_INSTALL_DIR = Join-Path $toolsDir 'python'
    $env:UV_PYTHON_BIN_DIR = Join-Path $toolsDir 'python-bin'
    $env:UV_PYTHON_INSTALL_REGISTRY = '0'
    $env:UV_NO_MODIFY_PATH = '1'
    $env:UV_LINK_MODE = 'copy'
    $env:UV_HTTP_TIMEOUT = '120'
    $env:UV_OFFLINE = if ($env:SRTP_OFFLINE -eq '1') { '1' } else { '0' }
    # uv's pinned release includes Python archive checksums. Never use a global interpreter.
    $basePython = Join-Path $env:UV_PYTHON_INSTALL_DIR ('cpython-' + $manifest.python + '-windows-x86_64-none\python.exe')
    if (-not (Test-Path -LiteralPath $basePython)) {
        Write-Host "[setup] Installing project Python $($manifest.python) ..."
        & $uvExe --no-config python install $manifest.python --no-bin --no-registry | Out-Host
        if ($LASTEXITCODE -ne 0) { throw 'Python download failed. Check network access to Astral/GitHub and retry.' }
    }
    # Include the absolute project path: copied/moved venvs are never silently reused.
    $rootHash = (Get-TextHash $Root).Substring(0, 12)
    $venvDir = Join-Path $toolsDir ('venv-' + $manifest.python + '-' + $rootHash)
    $pythonExe = Join-Path $venvDir 'Scripts\python.exe'
    $validPython = $false
    if (Test-Path -LiteralPath $pythonExe) {
        try {
            $actual = & $pythonExe -I -c 'import platform; print(platform.python_version())' 2>$null
            $validPython = ($LASTEXITCODE -eq 0 -and $actual -eq $manifest.python)
        } catch {}
    }
    if (-not $validPython) {
        Save-BrokenRuntime $venvDir $runtime
        & $uvExe --no-config venv --python $basePython $venvDir | Out-Host
        if ($LASTEXITCODE -ne 0) { throw 'Project virtual environment creation failed.' }
    }

    $lock = Join-Path $backend 'requirements.lock.txt'
    $stamp = Join-Path $venvDir 'requirements.sha256'
    $lockHash = (Get-FileHash -LiteralPath $lock -Algorithm SHA256).Hash
    $checkScript = Join-Path $Root 'scripts\check_environment.py'
    $checkOutput = & $pythonExe -I $checkScript $lock
    $healthy = ($LASTEXITCODE -eq 0)
    if (-not $healthy -or -not (Test-Stamp $stamp $lockHash)) {
        Write-Host '[setup] Synchronizing locked Python dependencies ...'
        $index = if ($env:SRTP_PYPI_INDEX) { $env:SRTP_PYPI_INDEX } else { 'https://pypi.org/simple' }
        $syncArgs = @('--no-config', 'pip', 'sync', '--python', $pythonExe, '--only-binary', ':all:', '--default-index', $index, $lock)
        if (-not $healthy) { $syncArgs += '--reinstall' }
        & $uvExe @syncArgs | Out-Host
        if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. See the locked package error above; check network/index availability and retry.' }
        & $pythonExe -I $checkScript $lock | Out-Host
        if ($LASTEXITCODE -ne 0) { throw 'Python dependency verification failed.' }
        Write-Utf8 $stamp $lockHash
    }

    $nodeDir = Join-Path $toolsDir ('node-v' + $manifest.node.version + '-win-x64')
    $nodeExe = Join-Path $nodeDir 'node.exe'
    if (-not (Test-Path -LiteralPath $nodeExe)) {
        $nodeZip = Join-Path $toolsDir ('node-' + $manifest.node.version + '.zip')
        Save-VerifiedDownload $manifest.node.url $nodeZip $manifest.node.sha256
        $staging = Join-Path $toolsDir ('extract-' + [guid]::NewGuid().ToString('N'))
        [IO.Compression.ZipFile]::ExtractToDirectory($nodeZip, $staging)
        Save-BrokenRuntime $nodeDir $runtime
        Move-Item -LiteralPath (Join-Path $staging ('node-v' + $manifest.node.version + '-win-x64')) -Destination $nodeDir
    }
    $nodeVersion = & $nodeExe --version
    if ($LASTEXITCODE -ne 0 -or $nodeVersion -ne ('v' + $manifest.node.version)) { throw "Invalid Node executable: $nodeExe" }
    # npm lifecycle scripts must also use this Node, even when PATH has a different version.
    $env:PATH = $nodeDir + ';' + $env:PATH
    $env:npm_config_cache = Join-Path $toolsDir 'npm-cache'
    $env:npm_config_offline = if ($env:SRTP_OFFLINE -eq '1') { 'true' } else { 'false' }
    $frontendHash = Get-TextHash ($Root + $manifest.node.version +
        (Get-FileHash -LiteralPath (Join-Path $frontend 'package-lock.json')).Hash +
        (Get-FileHash -LiteralPath (Join-Path $frontend 'package.json')).Hash)
    $frontendStamp = Join-Path $runtime 'frontend-v2.sha256'
    $healthyFrontend = $false
    Push-Location -LiteralPath $frontend
    try {
        if (Test-Stamp $frontendStamp $frontendHash) {
            try {
                & $nodeExe --input-type=module -e "await import('vite')" 2>$null | Out-Host
                $healthyFrontend = ($LASTEXITCODE -eq 0)
            } catch { $healthyFrontend = $false }
        }
        if (-not $healthyFrontend) {
            Write-Host '[setup] Synchronizing locked frontend dependencies (npm ci) ...'
            $registry = if ($env:SRTP_NPM_REGISTRY) { $env:SRTP_NPM_REGISTRY } else { 'https://registry.npmjs.org' }
            & $nodeExe (Join-Path $nodeDir 'node_modules\npm\bin\npm-cli.js') ci --no-audit --no-fund --registry $registry | Out-Host
            if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed. Check network/registry availability and retry.' }
            & $nodeExe --input-type=module -e "await import('vite')" | Out-Host
            if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency verification failed.' }
            Write-Utf8 $frontendStamp $frontendHash
        }
    } finally { Pop-Location }

    $envFile = Join-Path $backend '.env'
    if (-not (Test-Path -LiteralPath $envFile)) { Copy-Item -LiteralPath (Join-Path $backend '.env.example') -Destination $envFile }
    $envText = [IO.File]::ReadAllText($envFile)
    if ($envText -notmatch '(?m)^SECRET_KEY=\S+\r?$' -or $envText -match 'SECRET_KEY=replace-with-a-new-random-secret-before-running') {
        $randomBytes = New-Object byte[] 32
        $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
        try { $rng.GetBytes($randomBytes) } finally { $rng.Dispose() }
        $secret = ([BitConverter]::ToString($randomBytes)).Replace('-', '').ToLowerInvariant()
        if ($envText -match '(?m)^SECRET_KEY=') { $envText = [regex]::Replace($envText, '(?m)^SECRET_KEY=[^\r\n]*', ('SECRET_KEY=' + $secret)) }
        else { $envText = $envText.TrimEnd() + "`r`nSECRET_KEY=$secret`r`n" }
        Write-Utf8 $envFile $envText
        Write-Host '[setup] Generated a local SECRET_KEY.'
    }
    return @{ python = $pythonExe; node = $nodeExe; uv = $uvExe; nodeDir = $nodeDir }
}
