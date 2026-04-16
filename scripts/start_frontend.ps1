$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = "D:\Anaconda\envs\SeeMusic\python.exe"
$port = 5173

if (-not (Test-Path $pythonExe)) {
    throw "Python environment not found: $pythonExe"
}

Set-Location $repoRoot
& $pythonExe -m http.server $port --directory "frontend"
