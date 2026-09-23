param(
    [switch]$Reinstall
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$venv = Join-Path $root '.venv-web'
$requirements = Join-Path $root 'requirements-web.txt'
$python = $null

foreach ($candidate in @('py', 'python')) {
    $command = Get-Command $candidate -ErrorAction SilentlyContinue
    if ($command) {
        $python = $command.Source
        break
    }
}
if (-not $python) {
    Write-Error 'Python was not found. Install Python 3.10+ and ensure python or py is on PATH.'
    exit 1
}

$venvPython = Join-Path $venv 'Scripts\python.exe'
if (-not (Test-Path $venvPython)) {
    Write-Host "Creating web environment at $venv"
    & $python -m venv $venv
    if ($LASTEXITCODE -ne 0) { throw "Could not create .venv-web (exit code $LASTEXITCODE)." }
}

$needsInstall = $Reinstall -or -not (Test-Path (Join-Path $venv '.web-ready'))
if (-not $needsInstall) {
    & $venvPython -c 'import flask' 2>$null
    $needsInstall = $LASTEXITCODE -ne 0
}
if ($needsInstall) {
    Write-Host 'Installing web dependencies. The first install may require internet access.'
    & $venvPython -m pip install -r $requirements
    if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed (exit code $LASTEXITCODE)." }
    New-Item -ItemType File -Force -Path (Join-Path $venv '.web-ready') | Out-Null
}

$listeners = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($listeners) {
    Write-Error 'Port 8000 is already in use. Stop the existing service or choose another port before starting.'
    exit 1
}

Set-Location $root
Write-Host 'Starting local web app at http://127.0.0.1:8000'
Write-Host 'Press Ctrl+C to stop the server.'
& $venvPython -m webapp.app
if ($LASTEXITCODE -ne 0) {
    Write-Error "The web server stopped with exit code $LASTEXITCODE. It was not started successfully."
    exit $LASTEXITCODE
}