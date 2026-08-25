param(
  [string]$Query,
  [string]$CatalogDir = ""
)

$ErrorActionPreference = "Stop"

if (-not $CatalogDir) {
  $CatalogDir = Join-Path $PSScriptRoot "..\catalog"
}
$CatalogDir = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($CatalogDir)
$apiPath = Join-Path $CatalogDir "r21_api_catalog.json"
$frameworkPath = Join-Path $CatalogDir "r21_framework_catalog.json"
$coveragePath = Join-Path $CatalogDir "capability_coverage.json"

if (-not $Query) {
  Write-Host "Usage: find_r21_api.ps1 -Query <header|framework|capability>"
  exit 2
}

if (Test-Path -LiteralPath $apiPath) {
  $api = Get-Content -LiteralPath $apiPath -Raw | ConvertFrom-Json
  $api.headers |
    Where-Object { $_.header -like "*$Query*" -or $_.framework -like "*$Query*" -or $_.relative_path -like "*$Query*" } |
    Select-Object header, framework, status, relative_path
}

if (Test-Path -LiteralPath $frameworkPath) {
  $frameworks = Get-Content -LiteralPath $frameworkPath -Raw | ConvertFrom-Json
  $frameworks.frameworks |
    Where-Object { $_.framework -like "*$Query*" } |
    Select-Object framework, status, root
}

if (Test-Path -LiteralPath $coveragePath) {
  $coverage = Get-Content -LiteralPath $coveragePath -Raw | ConvertFrom-Json
  $coverage.capabilities |
    Where-Object { $_.capability_id -like "*$Query*" -or $_.family -like "*$Query*" -or $_.extractor -like "*$Query*" } |
    Select-Object capability_id, family, status, extractor, fixture_verified, reconstruction_verified
}
