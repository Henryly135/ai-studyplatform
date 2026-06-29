$ErrorActionPreference = "Stop"

$RootDir = Resolve-Path (Join-Path $PSScriptRoot "..")
$ComposeFile = Join-Path $RootDir "infra/docker-compose.yml"
$EnvFile = Join-Path $RootDir ".env"
$Services = @(
  "identity-service",
  "communication-service",
  "learning-service",
  "ai-service"
)

Set-Location $RootDir

foreach ($Service in $Services) {
  Write-Output "==> Running pytest for $Service"
  docker compose --env-file $EnvFile -f $ComposeFile exec -T $Service pytest tests -q
  if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
  }
}

Write-Output "All backend service tests passed."
