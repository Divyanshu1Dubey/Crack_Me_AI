<#
.SYNOPSIS
  Stop the local CrackLabs stack started by start-local.ps1.

.PARAMETER KeepDatabase
  Leave the isolated PostgreSQL cluster (port 55432) running.
#>
param(
    [string]$LocalRoot = (Join-Path $env:USERPROFILE 'crack_local'),
    [string]$PgBin = 'C:\Program Files\PostgreSQL\16\bin',
    [switch]$KeepDatabase
)

$Run = Join-Path $LocalRoot 'run'
foreach ($name in 'frontend', 'backend') {
    $pidFile = Join-Path $Run "$name.pid"
    if (Test-Path $pidFile) {
        $procId = (Get-Content $pidFile | Select-Object -First 1).Trim()
        if ($procId) {
            # /T also stops child processes (Next.js workers, runserver child).
            & taskkill.exe /PID $procId /T /F 2>$null | Out-Null
            Write-Host "Stopped $name (pid $procId)"
        }
        Remove-Item $pidFile -Force
    } else {
        Write-Host "${name}: no pid file (not started by start-local.ps1?)"
    }
}

if (-not $KeepDatabase) {
    $PgData = Join-Path $LocalRoot 'pgdata'
    if (Test-Path (Join-Path $PgData 'postmaster.pid')) {
        & (Join-Path $PgBin 'pg_ctl.exe') -D $PgData -m fast stop
    } else {
        Write-Host 'PostgreSQL (55432) not running.'
    }
}
