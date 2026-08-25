param(
  [Parameter(Mandatory=$true)][string]$OldExe,
  [Parameter(Mandatory=$true)][string]$NewExe,
  [Parameter(Mandatory=$true)][Alias("Input")][string]$InputPath,
  [Parameter(Mandatory=$true)][string]$OldOutput,
  [Parameter(Mandatory=$true)][string]$NewOutput,
  [Parameter(Mandatory=$true)][string]$ReportOutput
)

$ErrorActionPreference = "Stop"

function RepoRoot {
  $scriptDir = $PSScriptRoot
  if ([string]::IsNullOrEmpty($scriptDir)) { $scriptDir = Split-Path -Parent $PSCommandPath }
  if ([string]::IsNullOrEmpty($scriptDir)) { $scriptDir = (Resolve-Path ".").Path }
  return (Resolve-Path (Join-Path $scriptDir "..\..")).Path
}

function Read-JsonLines($path) {
  $items = @()
  if (!(Test-Path $path)) { return $items }
  Get-Content $path | ForEach-Object {
    if ($_.Trim().Length -gt 0) {
      $items += ($_ | ConvertFrom-Json)
    }
  }
  return $items
}

function Feature-Key($feature) {
  $startup = ""
  if ($feature.PSObject.Properties["startup_type"]) { $startup = [string]$feature.startup_type }
  $source = 0
  if ($feature.PSObject.Properties["source_index"]) { $source = [int]$feature.source_index }
  elseif ($feature.PSObject.Properties["native_enumeration_index"]) { $source = [int]$feature.native_enumeration_index }
  return ([string]$feature.tree_path) + "|" + $startup + "|" + $source
}

function Parent-Path($feature, $byId) {
  $parentId = ""
  if ($feature.PSObject.Properties["parent_id"]) { $parentId = [string]$feature.parent_id }
  if ($parentId.Length -eq 0) { return "" }
  if (!$byId.ContainsKey($parentId)) { return "__missing_parent__" }
  return [string]$byId[$parentId].tree_path
}

function Run-CaaProgram($exe, $inputPath, $outputPath) {
  $radeSetenv = Join-Path $env:CAA_RADE_ROOT "intel_a\code\command\MkmkSetenv.bat"
  if (!(Test-Path $radeSetenv)) { throw "RADE setenv not found: $radeSetenv" }
  $cmd = "call `"$radeSetenv`" >nul && set _MkmkOS_BitMode=64 && set PATH=$env:PATH && `"$exe`" --input `"$inputPath`" --output `"$outputPath`" --pretty"
  & cmd /c $cmd
  if ($LASTEXITCODE -ne 0) { throw "parser failed with exit code ${LASTEXITCODE}: $exe" }
}

$root = RepoRoot
if ([string]::IsNullOrEmpty($env:CAA_RADE_ROOT)) { $env:CAA_RADE_ROOT = Join-Path $root ".caa_toolchain_links\rade21" }
if ([string]::IsNullOrEmpty($env:CAA_PREREQ_ROOT)) { $env:CAA_PREREQ_ROOT = Join-Path $root ".caa_toolchain_links\catia21" }
$env:_MkmkOS_BitMode = "64"
$env:MkmkINSTALL_PATH = $env:CAA_RADE_ROOT
$env:PATH = (Join-Path $env:CAA_PREREQ_ROOT "win_b64\code\bin") + ";" +
            (Join-Path $root "caa_new\win_b64\code\bin") + ";" +
            (Join-Path $root "3DjiexiCAA\win_b64\code\bin") + ";" + $env:PATH

if (!(Test-Path $OldExe)) { throw "OldExe not found: $OldExe" }
if (!(Test-Path $NewExe)) { throw "NewExe not found: $NewExe" }
if (!(Test-Path $InputPath)) { throw "Input not found: $InputPath" }

Run-CaaProgram $OldExe $InputPath $OldOutput
Run-CaaProgram $NewExe $InputPath $NewOutput

$oldFeatures = Read-JsonLines (Join-Path $OldOutput "features.jsonl")
$newFeatures = Read-JsonLines (Join-Path $NewOutput "features.jsonl")
$newEntities = Read-JsonLines (Join-Path $NewOutput "object_entities.jsonl")
$newRelations = Read-JsonLines (Join-Path $NewOutput "relations.jsonl")

$oldById = @{}
foreach ($f in $oldFeatures) { $oldById[[string]$f.feature_id] = $f }
$newById = @{}
foreach ($f in $newFeatures) { $newById[[string]$f.feature_id] = $f }

$oldPrimary = @{}
foreach ($f in $oldFeatures) {
  $key = Feature-Key $f
  if (!$oldPrimary.ContainsKey($key)) { $oldPrimary[$key] = @() }
  $oldPrimary[$key] += $f
}

$newPrimary = @{}
$duplicatePrimaryPaths = @()
$supplementalPaths = @()
foreach ($f in $newFeatures) {
  $presentation = ""
  if ($f.PSObject.Properties["presentation_status"]) { $presentation = [string]$f.presentation_status }
  if ($presentation -eq "non_primary") {
    $supplementalPaths += [string]$f.tree_path
    continue
  }
  $key = Feature-Key $f
  if (!$newPrimary.ContainsKey($key)) { $newPrimary[$key] = @() }
  $newPrimary[$key] += $f
}
foreach ($key in $newPrimary.Keys) {
  if ($newPrimary[$key].Count -gt 1) { $duplicatePrimaryPaths += $key }
}

$missing = @()
$extra = @()
$matched = 0
$parentMismatches = @()
$sourceOrderMismatches = @()
$displayNameMismatches = @()
$startupTypeMismatches = @()

foreach ($key in $oldPrimary.Keys) {
  if (!$newPrimary.ContainsKey($key)) {
    $missing += $key
    continue
  }
  $matched += 1
  $old = $oldPrimary[$key][0]
  $new = $newPrimary[$key][0]
  if ((Parent-Path $old $oldById) -ne (Parent-Path $new $newById)) { $parentMismatches += $key }
  $oldSource = if ($old.PSObject.Properties["native_enumeration_index"]) { [int]$old.native_enumeration_index } else { 0 }
  $newSource = if ($new.PSObject.Properties["source_index"]) { [int]$new.source_index } else { 0 }
  if ($oldSource -ne $newSource) { $sourceOrderMismatches += $key }
  if ([string]$old.display_name -ne [string]$new.display_name) { $displayNameMismatches += $key }
  if ([string]$old.startup_type -ne [string]$new.startup_type) { $startupTypeMismatches += $key }
}
foreach ($key in $newPrimary.Keys) {
  if (!$oldPrimary.ContainsKey($key)) { $extra += $key }
}

$invalidParentCount = 0
foreach ($f in $newFeatures) {
  $parentId = ""
  if ($f.PSObject.Properties["parent_id"]) { $parentId = [string]$f.parent_id }
  if ($parentId.Length -gt 0 -and !$newById.ContainsKey($parentId)) { $invalidParentCount += 1 }
}

$legacyMissing = 0
foreach ($r in $newRelations) {
  if (!$newById.ContainsKey([string]$r.from_id) -or !$newById.ContainsKey([string]$r.to_id)) {
    $legacyMissing += 1
  }
}

$report = [ordered]@{
  old_object_count = $oldFeatures.Count
  new_entity_count = $newEntities.Count
  new_occurrence_count = $newFeatures.Count
  matched_by_path = $matched
  missing_primary_paths = $missing
  extra_primary_paths = $extra
  supplemental_paths = $supplementalPaths
  duplicate_primary_paths = $duplicatePrimaryPaths
  parent_mismatches = $parentMismatches
  source_order_mismatches = $sourceOrderMismatches
  display_name_mismatches = $displayNameMismatches
  startup_type_mismatches = $startupTypeMismatches
  invalid_parent_count = $invalidParentCount
  legacy_relation_endpoint_missing = $legacyMissing
}

$parent = Split-Path -Parent $ReportOutput
if ($parent -and !(Test-Path $parent)) { New-Item -ItemType Directory -Path $parent | Out-Null }
$report | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $ReportOutput
$report | ConvertTo-Json -Depth 8
