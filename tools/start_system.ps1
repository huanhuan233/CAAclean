param(
    [switch]$Check,
    [switch]$NoOpen
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$backend = Join-Path $root 'backend'
$frontend = Join-Path $root 'frontend'
$logs = Join-Path $root '.runtime\startup-logs'
$python = Join-Path $backend '.venv\Scripts\python.exe'
$vite = Join-Path $frontend 'node_modules\vite\bin\vite.js'
$envFile = Join-Path $backend '.env'
$capture = Join-Path $root 'caa_new\intel_a\code\bin\CadCapture.exe'
$started = New-Object System.Collections.Generic.List[System.Diagnostics.Process]

function Fail([string]$message) {
    throw $message
}

function Find-Node20 {
    $candidates = New-Object System.Collections.Generic.List[string]
    if ($env:CAD_NODE_EXE) { $candidates.Add($env:CAD_NODE_EXE) }
    Get-Command node.exe -All -ErrorAction SilentlyContinue | ForEach-Object { $candidates.Add($_.Source) }
    if (Test-Path -LiteralPath 'C:\nvm4w\nodejs\node.exe') { $candidates.Add('C:\nvm4w\nodejs\node.exe') }
    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        if (-not (Test-Path -LiteralPath $candidate)) { continue }
        try {
            $version = (& $candidate --version).TrimStart('v')
            if ([version]$version -ge [version]'20.19.0') { return $candidate }
        } catch { }
    }
    Fail 'Node.js >= 20.19 is required. Set CAD_NODE_EXE to a compatible node.exe.'
}

function Port-Owner([int]$port) {
    $listener = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($listener) { return $listener.OwningProcess }
    return $null
}

function Wait-Http([string]$url, [int]$seconds) {
    for ($i = 0; $i -lt $seconds; $i++) {
        try {
            $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -eq 200) { return $true }
        } catch { }
        Start-Sleep -Seconds 1
    }
    return $false
}

function Start-CadService([string]$name, [string]$exe, [string[]]$arguments, [string]$directory) {
    $out = Join-Path $logs "$name.out.log"
    $err = Join-Path $logs "$name.err.log"
    $process = Start-Process -FilePath $exe -ArgumentList $arguments -WorkingDirectory $directory -WindowStyle Hidden -RedirectStandardOutput $out -RedirectStandardError $err -PassThru
    $started.Add($process)
    Write-Host "$name PID=$($process.Id); logs: $out / $err"
}

try {
    if (-not (Test-Path -LiteralPath $envFile)) { Fail "Missing $envFile; configure database and CAA paths as described in README.md." }
    if (-not (Test-Path -LiteralPath $python)) { Fail "Missing $python; create the virtual environment and install backend/requirements.txt." }
    if (-not (Test-Path -LiteralPath $vite)) { Fail "Missing $vite; run pnpm install --frozen-lockfile in frontend." }
    $node = Find-Node20
    if (-not (Test-Path -LiteralPath $capture)) { Fail "Missing 32-bit CAA executable $capture; compile with caa_new/tools/build_r21_x86.bat." }
    $ports = @(5182, 5181, 9999)
    foreach ($port in $ports) {
        $ownerPid = Port-Owner $port
        if ($null -ne $ownerPid) { Fail "Port $port is used by PID $ownerPid. Inspect the old service before stopping it." }
    }
    Write-Host "Preflight passed: Python, Node $(& $node --version), CAA x86 executable, and service ports."
    if ($Check) { exit 0 }

    New-Item -ItemType Directory -Force -Path $logs | Out-Null
    # Both Python services read backend/.env; these process values pin the current CAA checkout and proxy ports.
    $env:APP_HOST = '127.0.0.1'
    $env:APP_PORT = '5181'
    $env:CATIA_WORKER_MODE = 'http'
    $env:CATIA_WORKER_URL = 'http://127.0.0.1:5182'
    $env:CAA_CAPTURE_PROJECT_ROOT = Join-Path $root 'caa_new'
    $env:CAA_CAPTURE_PLATFORM = 'intel_a'
    $env:CAA_CAPTURE_BITNESS = '32'

    Start-CadService 'worker' $python @('-m', 'uvicorn', 'app.catia_worker.server:app', '--host', '127.0.0.1', '--port', '5182') $backend
    if (-not (Wait-Http 'http://127.0.0.1:5182/health' 20)) { Fail 'CAA Worker health check failed; inspect worker.err.log.' }
    $workerHealth = Invoke-RestMethod -Uri 'http://127.0.0.1:5182/health' -TimeoutSec 5
    if (-not $workerHealth.accepting_jobs) { Fail 'CAA Worker is degraded and cannot accept jobs; inspect worker.err.log and the CAA paths in backend/.env.' }
    Start-CadService 'backend' $python @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '5181') $backend
    if (-not (Wait-Http 'http://127.0.0.1:5181/api/health/database' 30)) { Fail 'Backend or PostgreSQL health check failed; inspect backend.err.log and backend/.env.' }
    Start-CadService 'frontend' $node @("`"$vite`"", '--mode', 'test', '--host', '0.0.0.0', '--port', '9999', '--strictPort', '--no-open') $frontend
    if (-not (Wait-Http 'http://127.0.0.1:9999/' 30)) { Fail 'Frontend health check failed; inspect frontend.err.log.' }
    Write-Host 'Startup succeeded: http://127.0.0.1:9999/'
    Write-Host 'LAN access: http://HOST_IP:9999/ (allow inbound TCP 9999 in Windows Firewall if needed).'
    if (-not $NoOpen) { Start-Process 'http://127.0.0.1:9999/' | Out-Null }
} catch {
    Write-Error $_.Exception.Message
    foreach ($process in $started) {
        if (-not $process.HasExited) { & taskkill.exe /PID $process.Id /T /F 2>$null | Out-Null }
    }
    exit 1
}
