param(
  [string]$EnvFile = ""
)

$ErrorActionPreference = "Stop"

$RootDir = Resolve-Path (Join-Path $PSScriptRoot "..")
$ComposeFile = Join-Path $RootDir "infra/docker-compose.yml"
if ([string]::IsNullOrWhiteSpace($EnvFile)) {
  if (-not [string]::IsNullOrWhiteSpace($env:ENV_FILE)) {
    $EnvFile = $env:ENV_FILE
  } else {
    $EnvFile = Join-Path $RootDir ".env"
  }
}
if (-not [System.IO.Path]::IsPathRooted($EnvFile)) {
  $EnvFile = Join-Path $RootDir $EnvFile
}
$Services = @(
  "identity-service",
  "communication-service",
  "learning-service",
  "ai-service"
)

Set-Location $RootDir

if (-not (Test-Path $EnvFile)) {
  Write-Error @"
Missing env file: $EnvFile
Create one with:
  cp .env.example .env
or run with:
  .\scripts\run-backend-tests.ps1 -EnvFile .env.example
"@
}

foreach ($Service in $Services) {
  Write-Output "==> Running pytest for $Service"
  docker compose --env-file $EnvFile -f $ComposeFile exec -T $Service pytest tests -q
  if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
  }
}

Write-Output "All backend service tests passed."
