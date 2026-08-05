[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$RepoRoot,
  [ValidateSet("baseline","completion")][string]$Mode = "completion",
  [string]$FixturesDir = "",
  [string]$ResultsDir = "",
  [switch]$SkipGenerate,
  [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"
$TestPackRoot = Split-Path -Parent $PSScriptRoot
$RepoRoot = (Resolve-Path $RepoRoot).Path
if ([string]::IsNullOrWhiteSpace($FixturesDir)) {
  $FixturesDir = Join-Path $RepoRoot "tests\caa_completion\fixtures"
}
if ([string]::IsNullOrWhiteSpace($ResultsDir)) {
  $ResultsDir = Join-Path $RepoRoot "tests\caa_completion\results"
}
New-Item -ItemType Directory -Force -Path $FixturesDir | Out-Null
New-Item -ItemType Directory -Force -Path $ResultsDir | Out-Null
$ReportDir = Join-Path $ResultsDir "reports"
New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null

$CatalogPath = Join-Path $TestPackRoot "spec\fixture_catalog.json"
$ContractPath = if ($Mode -eq "baseline") {
  Join-Path $TestPackRoot "spec\current_contract.json"
} else {
  Join-Path $TestPackRoot "spec\completion_contract.json"
}
$Python = "python"

function Invoke-Checked([string]$FilePath, [string[]]$Arguments, [string]$Stage) {
  & $FilePath @Arguments
  if ($LASTEXITCODE -ne 0) { throw "$Stage failed with exit code $LASTEXITCODE" }
}

function Write-StateReport([string]$FixtureId, [string]$Status, [string]$Code, [string]$Message, [string]$Suffix) {
  $obj = [ordered]@{
    fixture_id = $FixtureId
    mode = $Mode
    status = $Status
    counts = @{ pass = 0; fail = $(if ($Status -eq "FAIL") {1} else {0}); blocked = $(if ($Status -eq "BLOCKED") {1} else {0}) }
    findings = @(@{ status = $Status; code = $Code; message = $Message; artifact = "" })
  }
  $path = Join-Path $ReportDir ($FixtureId + $Suffix + ".json")
  $obj | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $path
}

Write-Host "[1/6] Lint test catalog"
Invoke-Checked $Python @((Join-Path $PSScriptRoot "lint_catalog.py"), $CatalogPath) "catalog lint"

if (-not $SkipGenerate) {
  Write-Host "[2/6] Generate real CATIA fixtures"
  Invoke-Checked "cscript.exe" @("//nologo", (Join-Path $TestPackRoot "generators\generate_core_fixtures.vbs"), $FixturesDir) "core fixture generation"
  Invoke-Checked "cscript.exe" @("//nologo", (Join-Path $TestPackRoot "generators\generate_advanced_fixtures.vbs"), $FixturesDir) "advanced fixture probes"
  Invoke-Checked "cscript.exe" @("//nologo", (Join-Path $TestPackRoot "generators\generate_product_fixtures.vbs"), $FixturesDir) "CATProduct fixture probes"
  Invoke-Checked "cscript.exe" @("//nologo", (Join-Path $TestPackRoot "generators\prepare_fta_scaffolds.vbs"), $FixturesDir) "FTA fixture probes"
  Invoke-Checked "cscript.exe" @("//nologo", (Join-Path $TestPackRoot "generators\verify_real_fixtures.vbs"), $FixturesDir) "independent fixture reopen verification"
} else {
  Write-Host "[2/6] Fixture generation skipped"
}

$BuildBat = Join-Path $RepoRoot "tools\build_r21_x86.bat"
$RunBat = Join-Path $RepoRoot "tools\run_r21_x86.bat"
if (-not (Test-Path $BuildBat) -or -not (Test-Path $RunBat)) {
  throw "Repository adapter not found: tools\build_r21_x86.bat and tools\run_r21_x86.bat are required"
}

if (-not $SkipBuild) {
  Write-Host "[3/6] Build R21 x86 parser"
  & $BuildBat
  if ($LASTEXITCODE -ne 0) { throw "R21 build failed: $LASTEXITCODE" }
} else {
  Write-Host "[3/6] Build skipped"
}

Write-Host "[4/6] Run parser self-test"
& $RunBat --self-test
if ($LASTEXITCODE -ne 0) { throw "Parser self-test failed: $LASTEXITCODE" }

$Catalog = Get-Content -Raw -Encoding UTF8 $CatalogPath | ConvertFrom-Json
$PairRuns = @{}
Write-Host "[5/6] Parse each real fixture twice and validate"
foreach ($Fixture in $Catalog.fixtures) {
  $FixtureId = [string]$Fixture.id
  if ($Fixture.creation -eq "self_test") {
    Write-StateReport $FixtureId "PASS" "SELF_TEST_COVERED" "Registry synthetic cases are covered by --self-test; real registry status fixture is separate" ""
    continue
  }
  $FileTokens = ([string]$Fixture.file).Split('|')
  $runList = @()
  for ($i = 0; $i -lt $FileTokens.Count; $i++) {
    $token = $FileTokens[$i]
    if ($Fixture.creation -eq "reuse") {
      $InputPath = Join-Path $RepoRoot ([string]$Fixture.source)
    } else {
      $InputPath = Join-Path $FixturesDir $token
    }
    $suffix = if ($FileTokens.Count -gt 1) { "__v" + ($i + 1) } else { "" }
    if (-not (Test-Path $InputPath)) {
      $state = if ($Fixture.creation -in @("manual_required","auto_probe")) { "BLOCKED" } else { "FAIL" }
      Write-StateReport $FixtureId $state "FIXTURE_INPUT_MISSING" "Missing real fixture: $InputPath" $suffix
      continue
    }

    $safe = ($FixtureId + $suffix) -replace '[^A-Za-z0-9_.-]', '_'
    $OutA = Join-Path $ResultsDir ($safe + "_A")
    $OutB = Join-Path $ResultsDir ($safe + "_B")
    foreach ($out in @($OutA,$OutB)) {
      if (Test-Path $out) { Remove-Item -Recurse -Force $out }
    }
    & $RunBat --input $InputPath --output $OutA --read-only
    $ExitA = $LASTEXITCODE
    & $RunBat --input $InputPath --output $OutB --read-only
    $ExitB = $LASTEXITCODE
    if ($ExitA -ne 0 -or $ExitB -ne 0) {
      Write-StateReport $FixtureId "FAIL" "PARSER_RUN_FAILED" "Parser exits for $token: A=$ExitA B=$ExitB" $suffix
      continue
    }

    $Report = Join-Path $ReportDir ($safe + ".json")
    & $Python (Join-Path $PSScriptRoot "validate_caa_outputs.py") `
      --mode $Mode --contract $ContractPath --catalog $CatalogPath `
      --fixture-id $FixtureId --run-a $OutA --run-b $OutB --report $Report
    $runList += $OutA
  }
  if ($runList.Count -eq 2) {
    $PairReport = Join-Path $ReportDir ((($FixtureId + "__pair") -replace '[^A-Za-z0-9_.-]', '_') + ".json")
    & $Python (Join-Path $PSScriptRoot "validate_version_pair.py") `
      --fixture-id $FixtureId --run-v1 $runList[0] --run-v2 $runList[1] --report $PairReport
  }
}

Write-Host "[6/6] Summarize suite"
& $Python (Join-Path $PSScriptRoot "summarize_reports.py") --reports $ReportDir --catalog $CatalogPath --output $ResultsDir
$SummaryExit = $LASTEXITCODE
Write-Host "Report: $(Join-Path $ResultsDir 'suite_report.md')"
exit $SummaryExit
