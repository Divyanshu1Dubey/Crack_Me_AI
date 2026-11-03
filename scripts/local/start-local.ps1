<#
.SYNOPSIS
  Start the full CrackLabs stack locally on the restored backup.

.DESCRIPTION
  1. Isolated PostgreSQL 16 cluster (127.0.0.1:55432, data in $LocalRoot\pgdata)
  2. Django backend on http://127.0.0.1:8000 (DJANGO_ENV_FILE=.env.localdev)
  3. Next.js frontend on http://localhost:3000 (local auth + mock payments)

  Nothing here talks to production: the backend loads backend/.env.localdev
  (never backend/.env), auth is the dev-only local mode, payments are mocked
  and mail is written to $LocalRoot\mail.

.PARAMETER Frontend
  'dev' (default, hot reload via `next dev --webpack`) or 'prod'
  (`next build` + `next start`; slower to start, faster pages).

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\local\start-local.ps1
#>
param(
    [ValidateSet('dev', 'prod')] [string]$Frontend = 'dev',
    [string]$LocalRoot = (Join-Path $env:USERPROFILE 'crack_local'),
    [string]$PgBin = 'C:\Program Files\PostgreSQL\16\bin',
    [switch]$SkipFrontend,
    [switch]$SkipBackend,
    # Pending migrations are applied to the local database before the backend
    # starts (migrate_local.py refuses any non-local database).
    [switch]$SkipMigrate
)

$ErrorActionPreference = 'Stop'
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Backend = Join-Path $RepoRoot 'backend'
$FrontendDir = Join-Path $RepoRoot 'frontend'
$Logs = Join-Path $LocalRoot 'logs'
$Run = Join-Path $LocalRoot 'run'
New-Item -ItemType Directory -Force -Path $Logs, $Run, (Join-Path $LocalRoot 'mail') | Out-Null

function Find-Python {
    $dir = $RepoRoot
    for ($i = 0; $i -lt 5; $i++) {
        $candidate = Join-Path $dir '.venv\Scripts\python.exe'
        if (Test-Path $candidate) { return $candidate }
        $dir = Split-Path $dir -Parent
        if (-not $dir) { break }
    }
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    throw 'Python not found. Create the venv: python -m venv .venv; .venv\Scripts\pip install -r backend\requirements.txt'
}

function Test-Port([int]$Port) {
    # A real TCP connect: Get-NetTCPConnection does not always report the
    # listener state for processes started from another console.
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $iar = $client.BeginConnect('127.0.0.1', $Port, $null, $null)
        return ($iar.AsyncWaitHandle.WaitOne(700) -and $client.Connected)
    } catch {
        return $false
    } finally {
        $client.Close()
    }
}

function Wait-Http([string]$Url, [int]$Seconds = 120) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
            if ($r.StatusCode -lt 500) { return $true }
        } catch { Start-Sleep -Milliseconds 800 }
    }
    return $false
}

# ── 1. PostgreSQL ────────────────────────────────────────────────────────
$PgData = Join-Path $LocalRoot 'pgdata'
if (-not (Test-Path (Join-Path $PgData 'PG_VERSION'))) {
    throw "No database cluster at $PgData. See docs/LOCAL_DEVELOPMENT.md (restore section)."
}
if (Test-Port 55432) {
    Write-Host 'PostgreSQL already running on 55432'
} else {
    Write-Host 'Starting PostgreSQL on 127.0.0.1:55432 ...'
    # A server killed without a clean shutdown leaves postmaster.pid behind.
    $pidFile = Join-Path $PgData 'postmaster.pid'
    if (Test-Path $pidFile) {
        $oldPid = (Get-Content $pidFile -TotalCount 1).Trim()
        if (-not (Get-Process -Id $oldPid -ErrorAction SilentlyContinue)) { Remove-Item $pidFile -Force }
    }
    # No -Wait: Windows PowerShell waits for the whole process tree, and the
    # postgres server is a child of pg_ctl. Poll the port instead.
    Start-Process -FilePath (Join-Path $PgBin 'pg_ctl.exe') -ArgumentList @('-D', "`"$PgData`"", '-l', "`"$(Join-Path $Logs 'postgres.log')`"", 'start') -WindowStyle Hidden | Out-Null
    $deadline = (Get-Date).AddSeconds(90)
    while (-not (Test-Port 55432) -and (Get-Date) -lt $deadline) { Start-Sleep -Milliseconds 700 }
    if (-not (Test-Port 55432)) { throw "PostgreSQL did not start; see $Logs\postgres.log" }
}

# ── 2. Backend ───────────────────────────────────────────────────────────
if (-not $SkipBackend) {
    if (-not (Test-Path (Join-Path $Backend '.env.localdev'))) {
        throw 'backend/.env.localdev missing. Run: python scripts/local/make_env_localdev.py --with-ai-keys'
    }
    if (Test-Port 8000) {
        Write-Host 'Something is already listening on :8000 (backend not started).'
    } else {
        $python = Find-Python
        $env:DJANGO_ENV_FILE = '.env.localdev'
        $env:PYTHONUNBUFFERED = '1'
        if (-not $SkipMigrate) {
            Write-Host 'Applying pending migrations to the local database ...'
            $ErrorActionPreference = 'Continue'
            & $python (Join-Path $PSScriptRoot 'migrate_local.py') 2>&1 | Out-File (Join-Path $Logs 'migrate.log')
            $migrateExit = $LASTEXITCODE
            $ErrorActionPreference = 'Stop'
            if ($migrateExit -ne 0) { throw "Migrations failed or were refused (exit $migrateExit); see $Logs\migrate.log" }
        }
        Write-Host 'Starting Django backend on http://127.0.0.1:8000 ...'
        $p = Start-Process -FilePath $python -ArgumentList @('manage.py', 'runserver', '127.0.0.1:8000', '--noreload') `
            -WorkingDirectory $Backend -WindowStyle Hidden -PassThru `
            -RedirectStandardOutput (Join-Path $Logs 'backend.out.log') -RedirectStandardError (Join-Path $Logs 'backend.err.log')
        $p.Id | Set-Content (Join-Path $Run 'backend.pid')
        if (-not (Wait-Http 'http://127.0.0.1:8000/api/health/' 120)) { throw "Backend did not become healthy; see $Logs\backend.err.log" }
    }
}

# ── 3. Frontend ──────────────────────────────────────────────────────────
if (-not $SkipFrontend) {
    if (Test-Port 3000) {
        Write-Host 'Something is already listening on :3000 (frontend not started).'
    } else {
        $env:NEXT_PUBLIC_API_URL = 'http://localhost:8000/api'
        $env:NEXT_PUBLIC_API_FALLBACK_URL = 'http://localhost:8000/api'
        $env:NEXT_PUBLIC_AUTH_MODE = 'local'
        $env:NEXT_PUBLIC_PAYMENTS_MODE = 'mock'
        $env:NEXT_TELEMETRY_DISABLED = '1'
        # Local builds must not report local traffic to the production
        # analytics account (Simple Analytics loads without consent: it is
        # cookieless). GA stays consent-gated as in production.
        $env:NEXT_PUBLIC_SIMPLE_ANALYTICS_ENABLED = 'false'
        $nextBin = Join-Path $FrontendDir 'node_modules\next\dist\bin\next'
        if (-not (Test-Path $nextBin)) { throw 'frontend/node_modules missing. Run: cd frontend; npm ci' }
        if ($Frontend -eq 'prod') {
            Write-Host 'Building frontend (next build) ...'
            Push-Location $FrontendDir
            try {
                # Windows PowerShell 5.1 turns native stderr lines into errors,
                # which 'Stop' would make fatal on the first build warning.
                $ErrorActionPreference = 'Continue'
                & node $nextBin build 2>&1 | Out-File (Join-Path $Logs 'frontend.build.log')
                $buildExit = $LASTEXITCODE
            } finally { $ErrorActionPreference = 'Stop'; Pop-Location }
            if ($buildExit -ne 0) { throw "next build failed (exit $buildExit); see $Logs\frontend.build.log" }
            $nextArgs = @($nextBin, 'start', '-p', '3000')
        } else {
            $nextArgs = @($nextBin, 'dev', '--webpack', '-p', '3000')
        }
        Write-Host "Starting Next.js ($Frontend) on http://localhost:3000 ..."
        $p = Start-Process -FilePath 'node' -ArgumentList $nextArgs -WorkingDirectory $FrontendDir -WindowStyle Hidden -PassThru `
            -RedirectStandardOutput (Join-Path $Logs 'frontend.out.log') -RedirectStandardError (Join-Path $Logs 'frontend.err.log')
        $p.Id | Set-Content (Join-Path $Run 'frontend.pid')
        if (-not (Wait-Http 'http://localhost:3000/' 240)) { throw "Frontend did not start; see $Logs\frontend.err.log" }
    }
}

Write-Host ''
Write-Host 'CrackLabs is running locally:'
Write-Host '  Frontend  http://localhost:3000'
Write-Host '  Backend   http://127.0.0.1:8000/api/health/'
Write-Host '  Admin     http://127.0.0.1:8000/admin/'
Write-Host '  Accounts  student@local.test / premium@local.test / admin@local.test'
Write-Host '            (password = LOCAL_SEED_PASSWORD in backend/.env.localdev)'
Write-Host "  Logs      $Logs"
Write-Host 'Stop with: powershell -ExecutionPolicy Bypass -File scripts\local\stop-local.ps1'
