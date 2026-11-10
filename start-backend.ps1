$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDirectory = Join-Path $projectRoot "backend"
$python = Join-Path $backendDirectory ".venv\Scripts\python.exe"

if (!(Test-Path $python)) {
    throw "Backend virtual environment not found. Create backend\.venv first."
}

Set-Location $projectRoot
& $python (Join-Path $backendDirectory "run.py")
