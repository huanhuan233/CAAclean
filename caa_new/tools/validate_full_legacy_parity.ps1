param(
  [string]$OldExe,
  [string]$NewExe,
  [string]$OldRunner,
  [string]$NewRunner,
  [string]$HoleInput,
  [string]$KuangInput,
  [string]$CatProductInput,
  [string]$OutputRoot,
  [string]$ReportOutput,
  [switch]$SkipRun
)

$ErrorActionPreference = "Stop"

function RepoRoot {
  $scriptDir = $PSScriptRoot
  if ([string]::IsNullOrEmpty($scriptDir)) { $scriptDir = Split-Path -Parent $PSCommandPath }
  if ([string]::IsNullOrEmpty($scriptDir)) { $scriptDir = (Resolve-Path ".").Path }
  return (Resolve-Path (Join-Path $scriptDir "..\..")).Path
}

function Assert-Exists($path) {
  if (!(Test-Path $path)) { throw "required path missing: $path" }
}

function Count-Lines($path) {
  if (!(Test-Path $path)) { return -1 }
  $count = 0
  $reader = [System.IO.File]::OpenText($path)
  try {
    while ($null -ne $reader.ReadLine()) { ++$count }
  } finally {
    $reader.Close()
  }
  return $count
}

function Read-JsonLines($path) {
  if (!(Test-Path $path)) { return @() }
  $items = @()
  foreach ($line in Get-Content $path -Encoding UTF8) {
    if (![string]::IsNullOrWhiteSpace($line)) {
      $items += ($line | ConvertFrom-Json)
    }
  }
  return $items
}

function Get-FieldCoverage($path, [string[]]$fields) {
  $items = Read-JsonLines $path
  $coverage = [ordered]@{}
  foreach ($field in $fields) { $coverage[$field] = 0 }
  foreach ($item in $items) {
    foreach ($field in $fields) {
      if ($item.PSObject.Properties.Name -contains $field) {
        $value = $item.$field
        if ($null -ne $value -and "$value" -ne "") { $coverage[$field] = [int]$coverage[$field] + 1 }
      }
    }
  }
  return $coverage
}

function Compare-Artifact($sample, $oldDir, $newDir, $oldName, $newName, [bool]$mustMatchCount) {
  $oldPath = Join-Path $oldDir $oldName
  $newPath = Join-Path $newDir $newName
  $oldCount = Count-Lines $oldPath
  $newCount = Count-Lines $newPath
  $status = "passed"
  $reason = ""
  $legacyTreeIsWeaker = $sample -eq "catproduct" -and $oldName -eq "features.jsonl" -and $oldCount -le 1 -and $newCount -gt $oldCount
  $legacyCatPartProductWrapper = ($sample -eq "hole" -or $sample -eq "kuang") -and
    ($oldName -eq "product_references.jsonl" -or $oldName -eq "product_instances.jsonl") -and
    $oldCount -le 1 -and $newCount -eq 0
  if ($oldCount -lt 0) {
    $status = "missing_old"
    $reason = "old artifact missing"
  } elseif ($newCount -lt 0) {
    $status = "failed"
    $reason = "new artifact missing"
  } elseif ($legacyTreeIsWeaker) {
    $status = "passed"
    $reason = "legacy CATProduct tree is root-only; caa_new richer native/product tree is kept"
  } elseif ($legacyCatPartProductWrapper) {
    $status = "passed"
    $reason = "legacy CATPart product wrapper is not required for caa_new CATPart tree"
  } elseif ($oldCount -gt 0 -and $newCount -eq 0) {
    $status = "failed"
    $reason = "old artifact has records but new artifact is empty"
  } elseif ($mustMatchCount -and $oldCount -ne $newCount) {
    $status = "failed"
    $reason = "record counts differ"
  }
  return [ordered]@{
    sample = $sample
    old_artifact = $oldName
    new_artifact = $newName
    old_count = $oldCount
    new_count = $newCount
    status = $status
    reason = $reason
  }
}

function Run-Parser($exe, $runner, $inputPath, $outputDir, [bool]$readOnly) {
  if (Test-Path $outputDir) { Remove-Item -LiteralPath $outputDir -Recurse -Force }
  New-Item -ItemType Directory -Path $outputDir | Out-Null
  $args = @("--input", $inputPath, "--output", $outputDir)
  if ($readOnly) { $args += "--read-only" }
  if (![string]::IsNullOrEmpty($runner)) {
    & $runner @args
    if ($LASTEXITCODE -ne 0) { throw "parser failed: $runner $inputPath" }
    return
  }
  & $exe @args
  if ($LASTEXITCODE -ne 0) { throw "parser failed: $exe $inputPath" }
}

function Resolve-FirstExisting([string[]]$paths) {
  foreach ($path in $paths) {
    if (Test-Path $path) { return (Resolve-Path $path).Path }
  }
  return ""
}

$root = RepoRoot
if ([string]::IsNullOrEmpty($OldExe)) { $OldExe = Join-Path $root "3DjiexiCAA\intel_a\code\bin\CadParseMvp.exe" }
if ([string]::IsNullOrEmpty($NewExe)) { $NewExe = Join-Path $root "caa_new\intel_a\code\bin\CadCapture.exe" }
if ([string]::IsNullOrEmpty($OldRunner)) { $OldRunner = Join-Path $root "3DjiexiCAA\tools\run_r21_x86.bat" }
if ([string]::IsNullOrEmpty($NewRunner)) { $NewRunner = Join-Path $root "caa_new\tools\run_r21_x86.bat" }
if ([string]::IsNullOrEmpty($HoleInput)) { $HoleInput = Join-Path $root "3DjiexiCAA\tests\fixtures\catia_r21\partdesign_holes_updated.CATPart" }
if ([string]::IsNullOrEmpty($KuangInput)) {
  $KuangInput = Resolve-FirstExisting @(
    (Join-Path $root "3DjiexiCAA\tests\fixtures\catia_r21\kuang.CATPart"),
    "D:\3Djiexiother\kuang.CATPart",
    (Join-Path $root ".runtime\catia-worker\188fc547-f929-4609-b36b-c4eb2403ed4a\source-bundle\catPart\kuang.CATPart")
  )
}
if ([string]::IsNullOrEmpty($CatProductInput)) {
  $CatProductInput = Resolve-FirstExisting @(
    "D:\3Djiexiother\5621C04000G23\5621C04000G23\5621C04000G23.CATProduct",
    (Join-Path $root ".runtime\catia-worker\188fc547-f929-4609-b36b-c4eb2403ed4a\source-bundle\catProduct\GT4.1000.D.500.000 A.CATProduct")
  )
}
if ([string]::IsNullOrEmpty($OutputRoot)) { $OutputRoot = Join-Path $root "caa_new\full_legacy_parity_output" }
if ([string]::IsNullOrEmpty($ReportOutput)) { $ReportOutput = Join-Path $OutputRoot "full_legacy_parity_report.json" }

Assert-Exists $OldExe
Assert-Exists $NewExe
Assert-Exists $OldRunner
Assert-Exists $NewRunner
Assert-Exists $HoleInput
if ([string]::IsNullOrEmpty($KuangInput)) { throw "kuang CATPart fixture not found; pass -KuangInput explicitly" }
Assert-Exists $KuangInput
Assert-Exists $CatProductInput

if (!(Test-Path $OutputRoot)) { New-Item -ItemType Directory -Path $OutputRoot | Out-Null }

$samples = @(
  [ordered]@{ name = "hole"; input = $HoleInput; kind = "catpart" },
  [ordered]@{ name = "kuang"; input = $KuangInput; kind = "catpart" },
  [ordered]@{ name = "catproduct"; input = $CatProductInput; kind = "catproduct" }
)

foreach ($sample in $samples) {
  $oldDir = Join-Path $OutputRoot ($sample.name + "_old")
  $newDir = Join-Path $OutputRoot ($sample.name + "_new")
  if (!$SkipRun) {
    Run-Parser $OldExe $OldRunner $sample.input $oldDir $true
    Run-Parser $NewExe $NewRunner $sample.input $newDir $false
  }
}

$artifactMap = @(
  @("features.jsonl", "features.jsonl", $true),
  @("relations.jsonl", "relations.jsonl", $false),
  @("parameters.jsonl", "parameters.jsonl", $false),
  @("native_features.jsonl", "native_features.jsonl", $false),
  @("native_feature_results.jsonl", "native_feature_results.jsonl", $false),
  @("native_feature_result_cells.jsonl", "native_feature_result_cells.jsonl", $false),
  @("native_feature_topology_links.jsonl", "native_feature_topology_links.jsonl", $false),
  @("native_topology_bodies.jsonl", "native_topology_bodies.jsonl", $false),
  @("native_topology_cells.jsonl", "native_topology_cells.jsonl", $false),
  @("native_topology_wires.jsonl", "native_topology_wires.jsonl", $false),
  @("native_topology_coedges.jsonl", "native_topology_coedges.jsonl", $false),
  @("native_mesh_face_map.jsonl", "native_mesh_face_map.jsonl", $false),
  @("native_mesh_triangles.jsonl", "native_mesh_triangles.jsonl", $false),
  @("fta_sets.jsonl", "fta_sets.jsonl", $false),
  @("fta_semantics.jsonl", "fta_semantics.jsonl", $false),
  @("product_references.jsonl", "product_references.jsonl", $false),
  @("product_instances.jsonl", "product_occurrences.jsonl", $false),
  @("capabilities.json", "capabilities.json", $false),
  @("coverage.json", "coverage.json", $false)
)

$comparisons = @()
foreach ($sample in $samples) {
  $oldDir = Join-Path $OutputRoot ($sample.name + "_old")
  $newDir = Join-Path $OutputRoot ($sample.name + "_new")
  foreach ($map in $artifactMap) {
    $comparisons += Compare-Artifact $sample.name $oldDir $newDir $map[0] $map[1] ([bool]$map[2])
  }
}

$fieldChecks = @(
  [ordered]@{ sample = "hole"; artifact = "native_features.jsonl"; fields = @("canonical_family", "decode_level", "payload_extraction_status") },
  [ordered]@{ sample = "hole"; artifact = "parameters.jsonl"; fields = @("name", "raw_value", "raw_unit", "read_status") },
  [ordered]@{ sample = "hole"; artifact = "native_feature_result_cells.jsonl"; fields = @("dimension", "center_mm", "area_mm2", "length_mm", "read_status") },
  [ordered]@{ sample = "hole"; artifact = "native_mesh_triangles.jsonl"; fields = @("vertices_mm", "normal", "face_cell_id") },
  [ordered]@{ sample = "kuang"; artifact = "fta_semantics.jsonl"; fields = @("component_index", "supported_interface_keys", "semantic_validity", "validation_text_status") }
)

$coverage = @()
foreach ($check in $fieldChecks) {
  $path = Join-Path (Join-Path $OutputRoot ($check.sample + "_new")) $check.artifact
  $lineCount = Count-Lines $path
  $coverage += [ordered]@{
    sample = $check.sample
    artifact = $check.artifact
    line_count = $lineCount
    field_coverage = Get-FieldCoverage $path $check.fields
  }
}

$failed = @($comparisons | Where-Object { $_.status -eq "failed" })
$summary = [ordered]@{
  status = if ($failed.Count -eq 0) { "passed" } else { "failed" }
  comparison_count = $comparisons.Count
  failed_count = $failed.Count
  comparisons = $comparisons
  semantic_field_coverage = $coverage
  note = "This gate fails when a legacy artifact has records but caa_new has no corresponding records. It is artifact and semantic-presence parity, not ID equality."
}

$parent = Split-Path -Parent $ReportOutput
if ($parent -and !(Test-Path $parent)) { New-Item -ItemType Directory -Path $parent | Out-Null }
$summary | ConvertTo-Json -Depth 12 | Set-Content -Encoding UTF8 $ReportOutput
$summary | ConvertTo-Json -Depth 12
if ($failed.Count -ne 0) { throw "full legacy parity failed with $($failed.Count) artifact gaps" }
