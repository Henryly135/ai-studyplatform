[CmdletBinding()]
param(
  [string]$BaseUrl = $(if ($env:DEMO_BASE_URL) { $env:DEMO_BASE_URL } else { "http://localhost:8080" }),
  [string]$Email = $(if ($env:DEMO_LOGIN_EMAIL) { $env:DEMO_LOGIN_EMAIL } elseif ($env:DEFAULT_ADMIN_EMAIL) { $env:DEFAULT_ADMIN_EMAIL } else { "demo@example.com" }),
  [string]$Password = $(if ($env:DEMO_LOGIN_PASSWORD) { $env:DEMO_LOGIN_PASSWORD } elseif ($env:DEFAULT_ADMIN_PASSWORD) { $env:DEFAULT_ADMIN_PASSWORD } else { "LocalDemo123!" }),
  [string]$GeminiModelId = $(if ($env:DEMO_GEMINI_MODEL_ID) { $env:DEMO_GEMINI_MODEL_ID } else { "gemini:gemini-3.5-flash-lite" }),
  [switch]$CheckGemini
)

$ErrorActionPreference = "Stop"
$BaseUrl = $BaseUrl.TrimEnd("/")

function Invoke-JsonRequest {
  param(
    [Parameter(Mandatory = $true)][ValidateSet("Get", "Post")][string]$Method,
    [Parameter(Mandatory = $true)][string]$Uri,
    [hashtable]$Headers,
    [object]$Body
  )

  $options = @{
    Method = $Method
    Uri = $Uri
    Headers = $Headers
  }
  if ($null -ne $Body) {
    $options.ContentType = "application/json"
    $options.Body = $Body | ConvertTo-Json -Depth 8 -Compress
  }
  return Invoke-RestMethod @options
}

try {
  $login = Invoke-JsonRequest `
    -Method Post `
    -Uri "$BaseUrl/api/auth/login" `
    -Body @{ email = $Email; password = $Password }
} catch {
  throw "Demo login smoke failed. The endpoint must return a controlled authentication or availability response, not HTTP 500. $($_.Exception.Message)"
}

$accessToken = [string]$login.accessToken
if ([string]::IsNullOrWhiteSpace($accessToken)) {
  throw "Demo login smoke failed: login response did not include an access token."
}

$authHeaders = @{ Authorization = "Bearer $accessToken" }
$me = Invoke-JsonRequest -Method Get -Uri "$BaseUrl/api/auth/me" -Headers $authHeaders
if ([string]::IsNullOrWhiteSpace([string]$me.identity)) {
  throw "Demo login smoke failed: /api/auth/me did not identify the signed-in user."
}

Write-Output "DEMO_LOGIN_SMOKE_OK identity=$($me.identity)"

if (-not $CheckGemini) {
  exit 0
}

try {
  $switched = Invoke-JsonRequest `
    -Method Post `
    -Uri "$BaseUrl/api/auth/switch-role" `
    -Headers $authHeaders `
    -Body @{ identity = "Admin" }
} catch {
  throw "Gemini smoke failed while switching the local demo account to Admin. $($_.Exception.Message)"
}
$adminToken = [string]$switched.accessToken
if ([string]::IsNullOrWhiteSpace($adminToken)) {
  throw "Gemini smoke failed: unable to obtain the local demo Admin role token."
}

$adminHeaders = @{ Authorization = "Bearer $adminToken" }
try {
  $health = Invoke-JsonRequest `
    -Method Post `
    -Uri "$BaseUrl/api/ai/admin/ai/providers/gemini/health-check" `
    -Headers $adminHeaders
} catch {
  throw "Gemini smoke failed during the provider health check. $($_.Exception.Message)"
}
if ($health.status -ne "ready") {
  throw "Gemini smoke failed: provider health status was '$($health.status)'."
}

$requestId = "smoke-" + [Guid]::NewGuid().ToString("N")
$chatRequestBody = @{
  message = "In one short sentence, explain how regular practice supports learning."
  model_id = $GeminiModelId
  request_id = $requestId
}
try {
  $chat = Invoke-JsonRequest `
    -Method Post `
    -Uri "$BaseUrl/api/ai/chat" `
    -Headers $authHeaders `
    -Body $chatRequestBody
} catch {
  throw "Gemini smoke failed during the real chat request. $($_.Exception.Message)"
}

$chatData = $chat.data
if ($null -eq $chatData -or $chatData.status -ne "completed" -or [string]::IsNullOrWhiteSpace([string]$chatData.reply)) {
  throw "Gemini smoke failed: the chat request did not complete successfully."
}
if ([string]$chatData.provider -ne "gemini") {
  throw "Gemini smoke failed: expected provider 'gemini', received '$($chatData.provider)'."
}

try {
  $replayedChat = Invoke-JsonRequest `
    -Method Post `
    -Uri "$BaseUrl/api/ai/chat" `
    -Headers $authHeaders `
    -Body $chatRequestBody
} catch {
  throw "Gemini smoke failed during the idempotent replay. $($_.Exception.Message)"
}
$replayedData = $replayedChat.data
$originalSources = $chatData.sources | ConvertTo-Json -Depth 8 -Compress
$replayedSources = $replayedData.sources | ConvertTo-Json -Depth 8 -Compress
if (
  $replayedData.user_message_id -ne $chatData.user_message_id -or
  $replayedData.assistant_message_id -ne $chatData.assistant_message_id -or
  [string]$replayedData.model_id -ne [string]$chatData.model_id -or
  [string]$replayedData.provider -ne [string]$chatData.provider -or
  $replayedSources -ne $originalSources
) {
  throw "Gemini smoke failed: the idempotent replay did not preserve the original response metadata."
}

# Do not print credentials, tokens, prompts, or model output.  The line below
# is intentionally limited to stable non-sensitive execution metadata.
Write-Output "GEMINI_CHAT_SMOKE_OK provider=$($chatData.provider) model=$($chatData.model_id)"
