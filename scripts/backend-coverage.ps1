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
  Write-Output "==> Running coverage for $Service"
  docker compose --env-file $EnvFile -f $ComposeFile exec -T $Service pytest tests --cov=app --cov-report=json:coverage.json --cov-report=term-missing
  if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
  }
}

$TotalCovered = 0
$TotalStatements = 0

foreach ($Service in $Services) {
  $CoveragePath = Join-Path $RootDir "services\$Service\coverage.json"
  $CoverageContent = Get-Content $CoveragePath -Raw
  $TotalsMatch = [regex]::Matches($CoverageContent, '"totals"\s*:\s*\{([^{}]*)\}') | Select-Object -Last 1

  if ($null -eq $TotalsMatch) {
    throw "Unable to find totals in $CoveragePath"
  }

  $TotalsText = $TotalsMatch.Groups[1].Value
  $CoveredMatch = [regex]::Match($TotalsText, '"covered_lines"\s*:\s*(\d+)')
  $StatementsMatch = [regex]::Match($TotalsText, '"num_statements"\s*:\s*(\d+)')

  if (-not $CoveredMatch.Success -or -not $StatementsMatch.Success) {
    throw "Unable to read covered_lines or num_statements from $CoveragePath"
  }

  $Covered = [int]$CoveredMatch.Groups[1].Value
  $Statements = [int]$StatementsMatch.Groups[1].Value
  $Percent = if ($Statements -eq 0) { 100 } else { [math]::Round(($Covered / $Statements) * 100, 2) }

  Write-Output "$Service coverage: $Percent% ($Covered / $Statements)"

  $TotalCovered += $Covered
  $TotalStatements += $Statements
}

$TotalPercent = if ($TotalStatements -eq 0) { 100 } else { [math]::Round(($TotalCovered / $TotalStatements) * 100, 2) }
Write-Output "TOTAL backend coverage: $TotalPercent% ($TotalCovered / $TotalStatements)"

if ($TotalPercent -lt 80) {
  exit 1
}
