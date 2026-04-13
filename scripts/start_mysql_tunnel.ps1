param(
    [switch]$Background
)

$ErrorActionPreference = "Stop"

function Read-DotEnv {
    param([string]$Path)

    $result = @{}
    if (-not (Test-Path -LiteralPath $Path)) {
        return $result
    }

    foreach ($line in Get-Content -LiteralPath $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) {
            continue
        }

        $parts = $trimmed.Split("=", 2)
        $result[$parts[0].Trim()] = $parts[1].Trim().Trim("'`"")
    }

    return $result
}

$root = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $root ".env"
$config = Read-DotEnv -Path $envFile

$sshHost = $config["SSH_HOST"]
$sshUser = $config["SSH_USER"]
$sshPort = if ($config.ContainsKey("SSH_PORT")) { $config["SSH_PORT"] } else { "22" }
$sshKey = $config["SSH_KEY_FILE"]
$localPort = if ($config.ContainsKey("DB_PORT")) { $config["DB_PORT"] } else { "3307" }

if (-not $sshHost -or -not $sshUser -or -not $sshKey) {
    throw "Missing SSH_HOST, SSH_USER, or SSH_KEY_FILE in .env"
}

$sshArgs = @(
    "-i", $sshKey,
    "-p", $sshPort,
    "-N",
    "-L", "${localPort}:127.0.0.1:3306",
    "$sshUser@$sshHost"
)

if ($Background) {
    $process = Start-Process -FilePath "ssh" -ArgumentList $sshArgs -PassThru -WindowStyle Hidden
    Write-Output "Tunnel started. PID=$($process.Id) local=127.0.0.1:$localPort remote=${sshHost}:3306"
} else {
    & ssh @sshArgs
}
