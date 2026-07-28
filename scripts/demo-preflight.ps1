[CmdletBinding()]
param(
  [string]$BaseUrl = $(if ($env:DEMO_BASE_URL) { $env:DEMO_BASE_URL } else { "http://localhost:8080" }),
  [string]$AccessToken = $env:DEMO_ACCESS_TOKEN,
  [string]$AdminAccessToken = $env:DEMO_ADMIN_ACCESS_TOKEN,
  [string]$CourseUuid = $env:DEMO_COURSE_UUID,
  [string]$ModuleUuid = $env:DEMO_MODULE_UUID,
  [int]$Attempts = $(if ($env:DEMO_PREFLIGHT_ATTEMPTS) { [int]$env:DEMO_PREFLIGHT_ATTEMPTS } else { 30 }),
  [int]$IntervalSeconds = $(if ($env:DEMO_PREFLIGHT_INTERVAL_SECONDS) { [int]$env:DEMO_PREFLIGHT_INTERVAL_SECONDS } else { 2 })
)

$ErrorActionPreference = "Stop"
$BaseUrl = $BaseUrl.TrimEnd("/")

if ([string]::IsNullOrWhiteSpace($AccessToken)) {
  throw "DEMO_ACCESS_TOKEN or -AccessToken must contain an educator or learner access token with course access and AI_CHAT_USE"
}

if ([string]::IsNullOrWhiteSpace($AdminAccessToken)) {
  throw "DEMO_ADMIN_ACCESS_TOKEN or -AdminAccessToken must contain an administrator access token with AI governance access"
}

if ([string]::IsNullOrWhiteSpace($CourseUuid)) {
  throw "DEMO_COURSE_UUID or -CourseUuid must contain the course UUID to verify RAG coverage"
}

if ([string]::IsNullOrWhiteSpace($ModuleUuid)) {
  throw "DEMO_MODULE_UUID or -ModuleUuid must contain an accessible published module UUID to verify RAG coverage"
}

function Invoke-HealthCheck {
  param([Parameter(Mandatory = $true)][string]$Url)

  for ($attempt = 1; $attempt -le $Attempts; $attempt += 1) {
    try {
      Invoke-RestMethod -Method Get -Uri $Url | Out-Null
      return
    }
    catch {
      if ($attempt -eq $Attempts) {
        throw "Health check failed after $Attempts attempts: $Url"
      }
      Start-Sleep -Seconds $IntervalSeconds
    }
  }
}

Write-Output "Checking service health..."
@(
  "$BaseUrl/api/health",
  "$BaseUrl/api/learning/health",
  "$BaseUrl/api/communication/health",
  "$BaseUrl/api/ai/health"
) | ForEach-Object { Invoke-HealthCheck -Url $_ }

$courseHeaders = @{ Authorization = "Bearer $AccessToken" }
$adminHeaders = @{ Authorization = "Bearer $AdminAccessToken" }
if ($env:DEMO_TRIGGER_BACKFILL -eq "true") {
  Write-Output "Queuing multi-embedding backfill..."
  Invoke-RestMethod `
    -Method Post `
    -Uri "$BaseUrl/api/ai/admin/telemetry/index-jobs/reindex-all" `
    -Headers $adminHeaders | Out-Null
}
$catalogUrl = "$BaseUrl/api/ai/models"
$catalogUrl = (
  "${catalogUrl}?courseUuid=$([Uri]::EscapeDataString($CourseUuid))" +
  "&moduleUuid=$([Uri]::EscapeDataString($ModuleUuid))"
)

$catalog = $null
for ($attempt = 1; $attempt -le $Attempts; $attempt += 1) {
  $catalog = Invoke-RestMethod -Method Get -Uri $catalogUrl -Headers $courseHeaders
  $availableChatModels = @(
    $catalog.items | Where-Object {
      $_.available -eq $true -and (
        $_.capabilities.chat -eq $true -or
        @($_.capabilities) -contains "chat"
      )
    }
  )
  $notReady = @(
    $availableChatModels | Where-Object {
      $_.ragReady -ne $true -or [double]$_.indexCoverage -lt 1
    }
  )
  $availableChatProviders = (
    @($availableChatModels | ForEach-Object { $_.provider } | Sort-Object -Unique) -join ","
  )
  if (
    $availableChatModels.Count -gt 0 -and
    $availableChatProviders -eq "gemini,glm,openrouter" -and
    $notReady.Count -eq 0
  ) {
    break
  }
  if ($attempt -eq $Attempts) {
    throw "Course module multi-embedding coverage did not become ready"
  }
  Start-Sleep -Seconds $IntervalSeconds
}
$providerState = Invoke-RestMethod -Method Get -Uri "$BaseUrl/api/ai/admin/ai/providers" -Headers $adminHeaders

$expectedProviders = "gemini,glm,openrouter"
$catalogProviders = (@($catalog.items | ForEach-Object { $_.provider } | Sort-Object -Unique) -join ",")
$adminProviders = (@($providerState.providers | ForEach-Object { $_.provider } | Sort-Object) -join ",")

if ($catalogProviders -ne $expectedProviders -or $adminProviders -ne $expectedProviders) {
  throw "Provider catalog must contain exactly Gemini, GLM and OpenRouter"
}

$chatModels = @(
  $catalog.items | Where-Object {
    $_.supportsChat -eq $true -or
    $_.capabilities.chat -eq $true -or
    @($_.capabilities) -contains "chat"
  }
)
if ($chatModels.Count -eq 0) {
  throw "No chat models are available in the catalog"
}

$availableChatModels = @($chatModels | Where-Object { $_.available -eq $true })
$availableChatProviders = (
  @($availableChatModels | ForEach-Object { $_.provider } | Sort-Object -Unique) -join ","
)
if ($availableChatProviders -ne $expectedProviders) {
  throw "Gemini, GLM and OpenRouter must each expose at least one available chat model"
}

foreach ($model in $chatModels) {
  if ([string]::IsNullOrWhiteSpace([string]$model.pairedEmbeddingModelId)) {
    throw "Chat model $($model.modelId) has no paired embedding model"
  }
  if ([int]$model.embeddingDimension -ne 1024) {
    throw "Chat model $($model.modelId) does not use the required 1024 dimensions"
  }
}

foreach ($provider in @($providerState.providers)) {
  if ($provider.configured -ne $true -or $provider.healthStatus -ne "ready") {
    throw "Provider $($provider.provider) is not configured and healthy"
  }
}

foreach ($model in $availableChatModels) {
  if ($model.ragReady -ne $true -or [double]$model.indexCoverage -lt 1) {
    throw "Course index is not ready for $($model.modelId)"
  }
}

Write-Output "Provider summary:"
foreach ($model in $chatModels) {
  $chatModelName = if ($model.displayName) { $model.displayName } else { $model.name }
  $embeddingName = if ($model.pairedEmbeddingModelName) {
    $model.pairedEmbeddingModelName
  }
  else {
    $model.pairedEmbeddingModelId
  }
  $ragState = if ($null -ne $model.ragReady) { $model.ragReady } else { "not checked" }
  $coverage = if ($null -ne $model.indexCoverage) { $model.indexCoverage } else { "not checked" }
  Write-Output "- $($model.provider): $chatModelName -> $embeddingName | RAG=$ragState | coverage=$coverage"
}

Write-Output "Demo preflight passed."
