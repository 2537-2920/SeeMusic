$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = "D:\Anaconda\envs\SeeMusic\python.exe"

if (-not (Test-Path $pythonExe)) {
    throw "Python environment not found: $pythonExe"
}

Set-Location $repoRoot
& $pythonExe "backend/main.py"
