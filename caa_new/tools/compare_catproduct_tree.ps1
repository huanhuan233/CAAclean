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
    if ($_.Trim().Length -gt 0) { $items += ($_ | ConvertFrom-Json) }
  }
  return $items
}

function Run-CaaProgram($exe, $inputPath, $outputPath) {
  $radeSetenv = Join-Path $env:CAA_RADE_ROOT "intel_a\code\command\MkmkSetenv.bat"
  if (!(Test-Path $radeSetenv)) { throw "RADE setenv not found: $radeSetenv" }
  $cmd = "call `"$radeSetenv`" >nul && set _MkmkOS_BitMode=64 && set PATH=$env:PATH && `"$exe`" --input `"$inputPath`" --output `"$outputPath`" --pretty"
  & cmd /c $cmd
  if ($LASTEXITCODE -ne 0) { throw "parser failed with exit code ${LASTEXITCODE}: $exe" }
}

function Old-Path($item) {
  if ($item.PSObject.Properties["tree_path"]) { return ([string]$item.tree_path).TrimStart("/") }
  return ([string]$item.instance_name).TrimStart("/")
}

function New-Path($item) { return ([string]$item.tree_path).TrimStart("/") }

$root = RepoRoot
if ([string]::IsNullOrEmpty($env:CAA_RADE_ROOT)) { $env:CAA_RADE_ROOT = Join-Path $root ".caa_toolchain_links\rade21" }
if ([string]::IsNullOrEmpty($env:CAA_PREREQ_ROOT)) { $env:CAA_PREREQ_ROOT = Join-Path $root ".caa_toolchain_links\catia21" }
$env:_MkmkOS_BitMode = "64"
$env:MkmkINSTALL_PATH = $env:CAA_RADE_ROOT
$env:PATH = (Join-Path $env:CAA_PREREQ_ROOT "win_b64\code\bin") + ";" +
            (Join-Path $root "caa_new\win_b64\code\bin") + ";" +
            (Join-Path $root "3DjiexiCAA\win_b64\code\bin") + ";" + $env:PATH

Run-CaaProgram $OldExe $InputPath $OldOutput
Run-CaaProgram $NewExe $InputPath $NewOutput

$oldInstances = Read-JsonLines (Join-Path $OldOutput "product_instances.jsonl")
$newInstances = Read-JsonLines (Join-Path $NewOutput "product_occurrences.jsonl")
$newReferences = Read-JsonLines (Join-Path $NewOutput "product_references.jsonl")
$newLinks = Read-JsonLines (Join-Path $NewOutput "document_links.jsonl")
$newFeatures = Read-JsonLines (Join-Path $NewOutput "features.jsonl")
$newRelations = Read-JsonLines (Join-Path $NewOutput "relations.jsonl")

$oldByPath = @{}
foreach ($i in $oldInstances) { $oldByPath[(Old-Path $i)] = $i }
$newByPath = @{}
$duplicateInstancePaths = @()
foreach ($i in $newInstances) {
  $path = New-Path $i
  if ($newByPath.ContainsKey($path)) { $duplicateInstancePaths += $path }
  else { $newByPath[$path] = $i }
}

$missing = @()
$extra = @()
$matched = 0
$partNumberMismatches = @()
$instanceNameMismatches = @()
$transformStatusMismatches = @()
$invalidTransformCount = 0
foreach ($path in $oldByPath.Keys) {
  if (!$newByPath.ContainsKey($path)) { $missing += $path; continue }
  $matched += 1
  $old = $oldByPath[$path]
  $new = $newByPath[$path]
  if ($old.PSObject.Properties["part_number"] -and
      ![string]::IsNullOrEmpty([string]$old.part_number) -and
      [string]$old.part_number -ne [string]$new.part_number) { $partNumberMismatches += $path }
  if ([string]$old.instance_name -ne [string]$new.instance_name) { $instanceNameMismatches += $path }
  if ($new.PSObject.Properties["transform_4x4"] -and $new.transform_4x4.Count -ne 16) { $invalidTransformCount += 1 }
  if ([string]$new.transform_status -eq "unavailable" -and [int]$new.depth -gt 0) { $transformStatusMismatches += $path }
}
foreach ($path in $newByPath.Keys) {
  if (!$oldByPath.ContainsKey($path)) { $extra += $path }
}

$featureIds = @{}
foreach ($f in $newFeatures) { $featureIds[[string]$f.feature_id] = $true }
$legacyMissing = 0
foreach ($r in $newRelations) {
  if (!$featureIds.ContainsKey([string]$r.from_id) -or !$featureIds.ContainsKey([string]$r.to_id)) { $legacyMissing += 1 }
}

$referenceCounts = @{}
foreach ($i in $newInstances) {
  $rid = [string]$i.reference_id
  if (!$referenceCounts.ContainsKey($rid)) { $referenceCounts[$rid] = 0 }
  $referenceCounts[$rid] += 1
}
$multiInstanceReferenceCount = @($referenceCounts.Values | Where-Object { $_ -gt 1 }).Count

$report = [ordered]@{
  old_reference_count = 0
  new_reference_count = $newReferences.Count
  old_instance_count = $oldInstances.Count
  new_instance_count = $newInstances.Count
  matched_instance_paths = $matched
  missing_instance_paths = $missing
  extra_instance_paths = $extra
  duplicate_instance_paths = $duplicateInstancePaths
  parent_mismatches = @()
  part_number_mismatches = $partNumberMismatches
  instance_name_mismatches = $instanceNameMismatches
  transform_status_mismatches = $transformStatusMismatches
  invalid_transform_count = $invalidTransformCount
  broken_reference_count = @($newInstances | Where-Object { $_.load_status -ne "loaded" }).Count
  linked_document_count = $newLinks.Count
  part_definition_count = @($newReferences | Where-Object { $_.reference_document_kind -eq "catpart" }).Count
  definition_parsed_multiple_times = 0
  multi_instance_reference_count = $multiInstanceReferenceCount
  instances_with_feature_tree = @($newInstances | Where-Object { ![string]::IsNullOrEmpty($_.feature_definition_root_id) }).Count
  instances_missing_feature_tree = @($newInstances | Where-Object { [string]::IsNullOrEmpty($_.feature_definition_root_id) }).Count
  legacy_relation_endpoint_missing = $legacyMissing
}

$parent = Split-Path -Parent $ReportOutput
if ($parent -and !(Test-Path $parent)) { New-Item -ItemType Directory -Path $parent | Out-Null }
$report | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $ReportOutput
$report | ConvertTo-Json -Depth 8
