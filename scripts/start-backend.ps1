param(
    [int]$Port = 8000,
    [switch]$NoReload
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonExecutable = Join-Path $projectRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonExecutable)) {
    throw 'Project virtual environment missing. Run py -3.13 -m venv .venv and install backend/requirements.txt.'
}
Push-Location $projectRoot
try {
    $uvicornArguments = @('-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1', '--port', "$Port")
    if (-not $NoReload) { $uvicornArguments += '--reload' }
    & $pythonExecutable @uvicornArguments
    if ($LASTEXITCODE -ne 0) { throw "Backend exited with code $LASTEXITCODE" }
}
finally { Pop-Location }
