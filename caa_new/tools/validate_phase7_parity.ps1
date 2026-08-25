param(
  [string]$OldExe,
  [string]$NewExe,
  [string]$CatPartInput,
  [string]$CatProductInput,
  [string]$OutputRoot,
  [string]$ReportOutput
)

$ErrorActionPreference = "Stop"

function RepoRoot {
  $scriptDir = $PSScriptRoot
  if ([string]::IsNullOrEmpty($scriptDir)) { $scriptDir = Split-Path -Parent $PSCommandPath }
  if ([string]::IsNullOrEmpty($scriptDir)) { $scriptDir = (Resolve-Path ".").Path }
  return (Resolve-Path (Join-Path $scriptDir "..\..")).Path
}

function Read-Json($path) {
  return (Get-Content $path -Encoding UTF8 -Raw | ConvertFrom-Json)
}

function Count-Items($value) {
  if ($null -eq $value) { return 0 }
  return @($value).Count
}

function Assert-Equal($name, $actual, $expected) {
  if ($actual -ne $expected) {
    throw "$name expected $expected but was $actual"
  }
}

function Assert-ZeroItems($name, $value) {
  $count = Count-Items $value
  if ($count -ne 0) {
    throw "$name expected 0 items but had $count"
  }
}

function Assert-Exists($path) {
  if (!(Test-Path $path)) {
    throw "required artifact missing: $path"
  }
}

$root = RepoRoot
if ([string]::IsNullOrEmpty($OldExe)) { $OldExe = Join-Path $root "3DjiexiCAA\win_b64\code\bin\CadParseMvp.exe" }
if ([string]::IsNullOrEmpty($NewExe)) { $NewExe = Join-Path $root "caa_new\win_b64\code\bin\CadCapture.exe" }
if ([string]::IsNullOrEmpty($CatPartInput)) { $CatPartInput = Join-Path $root "3DjiexiCAA\tests\fixtures\catia_r21\partdesign_holes_updated.CATPart" }
if ([string]::IsNullOrEmpty($CatProductInput)) { $CatProductInput = Join-Path $root ".runtime\catia-worker\188fc547-f929-4609-b36b-c4eb2403ed4a\source-bundle\catProduct\GT4.1000.D.500.000 A.CATProduct" }
if ([string]::IsNullOrEmpty($OutputRoot)) { $OutputRoot = Join-Path $root "caa_new\phase7_parity_output" }
if ([string]::IsNullOrEmpty($ReportOutput)) { $ReportOutput = Join-Path $OutputRoot "phase7_parity_report.json" }

Assert-Exists $OldExe
Assert-Exists $NewExe
Assert-Exists $CatPartInput
Assert-Exists $CatProductInput

if (!(Test-Path $OutputRoot)) { New-Item -ItemType Directory -Path $OutputRoot | Out-Null }

$catpartReport = Join-Path $OutputRoot "catpart_comparison.json"
$catproductReport = Join-Path $OutputRoot "catproduct_comparison.json"
$catpartOld = Join-Path $OutputRoot "catpart_old"
$catpartNew = Join-Path $OutputRoot "catpart_new"
$catproductOld = Join-Path $OutputRoot "catproduct_old"
$catproductNew = Join-Path $OutputRoot "catproduct_new"

& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root "caa_new\tools\compare_catpart_tree.ps1") `
  -OldExe $OldExe `
  -NewExe $NewExe `
  -InputPath $CatPartInput `
  -OldOutput $catpartOld `
  -NewOutput $catpartNew `
  -ReportOutput $catpartReport
if ($LASTEXITCODE -ne 0) { throw "CATPart parity comparison failed" }

& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root "caa_new\tools\compare_catproduct_tree.ps1") `
  -OldExe $OldExe `
  -NewExe $NewExe `
  -InputPath $CatProductInput `
  -OldOutput $catproductOld `
  -NewOutput $catproductNew `
  -ReportOutput $catproductReport
if ($LASTEXITCODE -ne 0) { throw "CATProduct parity comparison failed" }

$part = Read-Json $catpartReport
$product = Read-Json $catproductReport

Assert-Equal "CATPart entity count" ([int]$part.new_entity_count) ([int]$part.old_object_count)
Assert-Equal "CATPart occurrence count" ([int]$part.new_occurrence_count) ([int]$part.old_object_count)
Assert-ZeroItems "CATPart duplicate primary paths" $part.duplicate_primary_paths
Assert-ZeroItems "CATPart parent mismatches" $part.parent_mismatches
Assert-ZeroItems "CATPart source-order mismatches" $part.source_order_mismatches
Assert-ZeroItems "CATPart display-name mismatches" $part.display_name_mismatches
Assert-ZeroItems "CATPart startup-type mismatches" $part.startup_type_mismatches
Assert-Equal "CATPart invalid parent count" ([int]$part.invalid_parent_count) 0
Assert-Equal "CATPart legacy relation endpoint missing" ([int]$part.legacy_relation_endpoint_missing) 0

Assert-Equal "CATProduct instance count" ([int]$product.new_instance_count) ([int]$product.old_instance_count)
Assert-Equal "CATProduct matched instance paths" ([int]$product.matched_instance_paths) ([int]$product.old_instance_count)
Assert-ZeroItems "CATProduct missing instance paths" $product.missing_instance_paths
Assert-ZeroItems "CATProduct extra instance paths" $product.extra_instance_paths
Assert-ZeroItems "CATProduct duplicate instance paths" $product.duplicate_instance_paths
Assert-ZeroItems "CATProduct part-number mismatches" $product.part_number_mismatches
Assert-ZeroItems "CATProduct instance-name mismatches" $product.instance_name_mismatches
Assert-ZeroItems "CATProduct transform-status mismatches" $product.transform_status_mismatches
Assert-Equal "CATProduct invalid transform count" ([int]$product.invalid_transform_count) 0
Assert-Equal "CATProduct broken reference count" ([int]$product.broken_reference_count) 0
Assert-Equal "CATProduct legacy relation endpoint missing" ([int]$product.legacy_relation_endpoint_missing) 0

$requiredNewArtifacts = @(
  "manifest.json",
  "capture_report.json",
  "reconstruction_plan.json",
  "object_entities.jsonl",
  "tree_occurrences.jsonl",
  "product_references.jsonl",
  "product_occurrences.jsonl",
  "document_links.jsonl",
  "property_facts.jsonl",
  "semantic_facets.jsonl",
  "topology_entities.jsonl",
  "geometry_entities.jsonl",
  "pmi_entities.jsonl",
  "feature_dependencies.jsonl",
  "topology_relations.jsonl",
  "pmi_associations.jsonl",
  "diagnostics.jsonl",
  "features.jsonl",
  "relations.jsonl",
  "parameters.jsonl",
  "native_features.jsonl",
  "native_topology.jsonl",
  "native_mesh_face_map.jsonl",
  "native_feature_results.jsonl",
  "native_feature_result_cells.jsonl",
  "native_feature_topology_links.jsonl",
  "fta_sets.jsonl",
  "fta_semantics.jsonl",
  "fta_topology_links.jsonl",
  "capabilities.json"
)

foreach ($name in $requiredNewArtifacts) {
  Assert-Exists (Join-Path $catpartNew $name)
  Assert-Exists (Join-Path $catproductNew $name)
}

$summary = [ordered]@{
  catpart = $part
  catproduct = $product
  required_artifacts_checked = $requiredNewArtifacts
  status = "passed"
}

$parent = Split-Path -Parent $ReportOutput
if ($parent -and !(Test-Path $parent)) { New-Item -ItemType Directory -Path $parent | Out-Null }
$summary | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $ReportOutput
$summary | ConvertTo-Json -Depth 8
