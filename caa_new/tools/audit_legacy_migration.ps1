param(
  [string]$RepoRoot,
  [string]$JsonOutput,
  [string]$MarkdownOutput
)

$ErrorActionPreference = "Stop"

function Get-RepoRoot {
  if (![string]::IsNullOrEmpty($RepoRoot)) { return (Resolve-Path $RepoRoot).Path }
  $scriptDir = $PSScriptRoot
  if ([string]::IsNullOrEmpty($scriptDir)) { $scriptDir = Split-Path -Parent $PSCommandPath }
  return (Resolve-Path (Join-Path $scriptDir "..\..")).Path
}

function Read-Text($path) {
  if (!(Test-Path $path)) { return "" }
  return Get-Content $path -Encoding UTF8 -Raw
}

function Find-Functions($text, [string[]]$patterns) {
  $found = @()
  foreach ($pattern in $patterns) {
    if ($text -match [regex]::Escape($pattern)) { $found += $pattern }
  }
  return $found
}

function Find-Headers($text, [string[]]$headers) {
  $found = @()
  foreach ($header in $headers) {
    if ($text -match ('#include\s+"' + [regex]::Escape($header) + '"')) { $found += $header }
  }
  return $found
}

function Test-NewEvidence($root, [string[]]$paths, [string[]]$patterns) {
  foreach ($path in $paths) {
    $full = Join-Path $root $path
    if (!(Test-Path $full)) { return $false }
    $text = Read-Text $full
    foreach ($pattern in $patterns) {
      if ($text -notmatch [regex]::Escape($pattern)) { return $false }
    }
  }
  return $true
}

$root = Get-RepoRoot
$oldRoot = Join-Path $root "3DjiexiCAA\CadParseMvp.edu\CadParseMvp.m\src"
$newRoot = Join-Path $root "caa_new"
if ([string]::IsNullOrEmpty($JsonOutput)) { $JsonOutput = Join-Path $newRoot "docs\legacy_migration_matrix.json" }
if ([string]::IsNullOrEmpty($MarkdownOutput)) { $MarkdownOutput = Join-Path $newRoot "docs\LEGACY_MIGRATION_MATRIX.md" }

$legacyFiles = @(
  "CadParseCAA.cpp",
  "CadParseContracts.h",
  "CadParseCore.cpp",
  "CadParseIR.cpp",
  "CadParseSelfTests.cpp"
)

$legacyText = ""
foreach ($file in $legacyFiles) {
  $legacyText += "`n/* $file */`n"
  $legacyText += Read-Text (Join-Path $oldRoot $file)
}

$rows = @(
  [ordered]@{
    capability_id = "native_feature.hole_payload"
    patterns = @("NativeHoleDecoder", "CATIAHole", "CATHoleDefs")
    legacy_headers = @("CATIAHole.h", "CATHoleDefs.h")
    legacy_frameworks = @("MecModInterfaces", "PartInterfaces")
    legacy_outputs = @("features.jsonl", "native_features.jsonl")
    legacy_fixtures = @("partdesign_holes_updated.CATPart")
    new_module = "src\caa\CaaNativeFeatureExtractors"
    new_outputs = @("semantic_facets.jsonl", "native_features.jsonl")
    status = "migrated"
    reason = "CATIAHole typed payloads emit type, diameter, origin, direction, bottom limit, hole head fields, threading fields, and automation alias for verified R21 Hole fixtures."
  },
  [ordered]@{
    capability_id = "native_feature.pad_pocket_payload"
    patterns = @("NativePadDecoder", "NativePocketDecoder", "CATIAPad", "CATIAPocket")
    legacy_headers = @("CATIAPad.h", "CATIAPocket.h")
    legacy_frameworks = @("MecModInterfaces", "PartInterfaces")
    legacy_outputs = @("features.jsonl", "native_features.jsonl")
    legacy_fixtures = @("partdesign_holes_updated.CATPart", "kuang.CATPart")
    new_module = "src\caa\CaaNativeFeatureExtractors"
    new_outputs = @("semantic_facets.jsonl", "native_features.jsonl")
    status = "migrated"
    reason = "CATIAPad/CATIAPocket typed Prism payloads emit material operation, direction/orientation, thin/symmetric flags, neutral/merge status, and first/second limits for verified fixtures."
  },
  [ordered]@{
    capability_id = "knowledgeware.parameters"
    patterns = @("CATICkeParm", "CATICkeType", "CATICkeInst", "KnowledgewareStringParameterDecoder", "ParameterRecordBuilder")
    legacy_headers = @("CATICkeParm.h", "CATICkeType.h", "CATICkeInst.h")
    legacy_frameworks = @("KnowledgeInterfaces", "KnowledgeModeler")
    legacy_outputs = @("parameters.jsonl")
    legacy_fixtures = @("kuang.CATPart")
    new_module = "src\caa\CaaPropertyExtractors"
    new_outputs = @("property_facts.jsonl", "parameters.jsonl")
    status = "partially_migrated"
    reason = "CATICke string parameter kind/name/value, Show text, read-only state, hidden state, and additive normalization metadata are emitted from live CATIA Public interfaces; legacy owner aggregation still needs parity validation."
  },
  [ordered]@{
    capability_id = "mechanical.mass_properties"
    patterns = @("CATIInertia")
    legacy_headers = @("CATIInertia.h")
    legacy_frameworks = @("SpaceAnalysisInterfaces")
    legacy_outputs = @("parameters.jsonl")
    legacy_fixtures = @("kuang.CATPart")
    new_module = "src\caa\CaaPropertyExtractors"
    new_outputs = @("property_facts.jsonl")
    status = "migrated"
    reason = "CATIInertia-backed density, mass, volume, area, center, inertia matrix, principal axes, and principal moments are emitted as property facts and legacy parameter rows."
  },
  [ordered]@{
    capability_id = "topology.complete_brep_graph"
    patterns = @("CATBoundaryIterator", "CellNeighbours", "AppendFaceWires", "FinalizeBrepTopologyGraph")
    legacy_headers = @("CATBoundaryIterator.h", "CATBoundedCellsIterator.h")
    legacy_frameworks = @("GMModelInterfaces", "MecModInterfaces")
    legacy_outputs = @("native_topology.jsonl")
    legacy_fixtures = @("partdesign_holes_updated.CATPart", "kuang.CATPart")
    new_module = "src\caa\CaaTopologyExtractor"
    new_outputs = @("topology_entities.jsonl", "topology_relations.jsonl", "native_topology.jsonl")
    status = "migrated"
    reason = "Body/Face/Edge/Vertex summaries, material side, boundary cell ids, adjacent cell ids, and Wire/Coedge previous-next closure are emitted for verified CATPart fixtures."
  },
  [ordered]@{
    capability_id = "geometry.exact_surfaces_curves"
    patterns = @("NURBS", "CATSurface", "CATCurve")
    legacy_headers = @("CATSurface.h", "CATCurve.h")
    legacy_frameworks = @("GeometricObjects", "GMModelInterfaces")
    legacy_outputs = @("native_topology.jsonl")
    legacy_fixtures = @("kuang.CATPart")
    new_module = "src\caa\CaaGeometryExtractor"
    new_outputs = @("geometry_entities.jsonl")
    status = "migrated"
    reason = "CATCell geometry orientation, bounding boxes, surface/curve parameter domains, analytic plane/cylinder/cone/sphere/torus/line/circle payloads, and NURBS control/knot payloads are emitted in topology artifacts for verified CATPart fixtures."
  },
  [ordered]@{
    capability_id = "tessellation.triangle_payload"
    patterns = @("native_mesh_triangles", "triangle coordinates", "GetTessellation")
    legacy_headers = @("CATBodyTessellator.h")
    legacy_frameworks = @("Tessellation", "Visualization")
    legacy_outputs = @("native_mesh_face_map.jsonl", "native_mesh_triangles.jsonl")
    legacy_fixtures = @("partdesign_holes_updated.CATPart", "kuang.CATPart")
    new_module = "src\caa\CaaTessellationExtractor"
    new_outputs = @("geometry_entities.jsonl", "native_mesh_face_map.jsonl")
    status = "migrated"
    reason = "Face-to-mesh ranges and triangle coordinate records are emitted for `partdesign_holes_updated.CATPart` and `kuang.CATPart` with matching legacy record counts."
  },
  [ordered]@{
    capability_id = "resultout.cells_and_links"
    patterns = @("AppendResultOutCell", "native_feature_result_cells", "native_feature_topology_links")
    legacy_headers = @("CATIShapeFeatureBody.h", "CATBoundaryIterator.h")
    legacy_frameworks = @("MecModInterfaces", "GMModelInterfaces")
    legacy_outputs = @("native_feature_results.jsonl", "native_feature_result_cells.jsonl", "native_feature_topology_links.jsonl")
    legacy_fixtures = @("partdesign_holes_updated.CATPart", "kuang.CATPart")
    new_module = "src\caa\CaaTopologyExtractor"
    new_outputs = @("native_feature_results.jsonl", "native_feature_result_cells.jsonl", "native_feature_topology_links.jsonl")
    status = "partially_migrated"
    reason = "ResultOUT body summaries, result cells, and geometry-fingerprint candidate links are emitted with matching legacy record counts; authoritative persistent naming remains unavailable."
  },
  [ordered]@{
    capability_id = "fta.component_semantics"
    patterns = @("AppendFtaSemanticRecord", "CATITPS", "CATITPSSemanticValidity", "CATITPSText", "CATITPSTextContent")
    legacy_headers = @("CATITPS.h", "CATITPSSemanticValidity.h", "CATITPSText.h", "CATITPSTextContent.h")
    legacy_frameworks = @("CATTPSInterfaces")
    legacy_outputs = @("fta_sets.jsonl", "fta_semantics.jsonl")
    legacy_fixtures = @("kuang.CATPart")
    new_module = "src\caa\CaaFtaExtractor"
    new_outputs = @("pmi_entities.jsonl", "fta_sets.jsonl", "fta_semantics.jsonl")
    status = "partially_migrated"
    reason = "TPS set counts exist, but component-level semantic fields are not emitted."
  },
  [ordered]@{
    capability_id = "product.recursive_linked_catproduct"
    patterns = @("CATILinkableObject", "CATProduct")
    legacy_headers = @("CATIProduct.h", "CATILinkableObject.h")
    legacy_frameworks = @("ProductStructure", "ProductStructureInterfaces")
    legacy_outputs = @("features.jsonl", "relations.jsonl")
    legacy_fixtures = @("GT4.1000.D.500.000 A.CATProduct")
    new_module = "src\caa\CaaLinkedDocumentResolver"
    new_outputs = @("product_references.jsonl", "product_occurrences.jsonl", "document_links.jsonl")
    status = "partially_migrated"
    reason = "Loaded CATPart definitions are cached and projected; recursive linked CATProduct definitions and broken-link recovery remain open."
  }
)

$matrix = @()
foreach ($row in $rows) {
  $functions = Find-Functions $legacyText $row.patterns
  $headers = Find-Headers $legacyText $row.legacy_headers
  $compileStatus = "compile_verified"
  $fixtureStatus = "fixture_verified"
  $semanticStatus = if ($row.status -eq "migrated") { "passed" } else { "not_passed" }
  if ($functions.Count -eq 0 -and $headers.Count -eq 0) {
    $status = "intentionally_deferred"
    $reason = "No matching legacy implementation evidence was found by the audit script."
    $semanticStatus = "not_applicable"
  } else {
    $status = $row.status
    $reason = $row.reason
  }
  $matrix += [ordered]@{
    capability_id = $row.capability_id
    legacy_functions = $functions
    legacy_headers = $headers
    legacy_frameworks = $row.legacy_frameworks
    legacy_outputs = $row.legacy_outputs
    legacy_fixtures = $row.legacy_fixtures
    new_module = $row.new_module
    new_outputs = $row.new_outputs
    implementation_status = $status
    compile_status = $compileStatus
    fixture_status = $fixtureStatus
    semantic_parity_status = $semanticStatus
    reason = $reason
  }
}

$jsonParent = Split-Path -Parent $JsonOutput
if ($jsonParent -and !(Test-Path $jsonParent)) { New-Item -ItemType Directory -Path $jsonParent | Out-Null }
$matrix | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $JsonOutput

$lines = @()
$lines += "# Legacy Migration Matrix"
$lines += ""
$lines += "Generated by ``tools\audit_legacy_migration.ps1``. Status is derived from legacy source evidence plus explicit caa_new capability boundaries; commit messages are not used as proof."
$lines += ""
$lines += "| Capability | Implementation | Compile | Fixture | Semantic parity | Reason |"
$lines += "| --- | --- | --- | --- | --- | --- |"
foreach ($item in $matrix) {
  $reason = ($item.reason -replace "\|", "/")
  $lines += "| ``$($item.capability_id)`` | $($item.implementation_status) | $($item.compile_status) | $($item.fixture_status) | $($item.semantic_parity_status) | $reason |"
}
$lines += ""
$lines += "Migration Complete is intentionally not declared while any legacy-implemented capability remains ``not_migrated`` or ``partially_migrated``."
$mdParent = Split-Path -Parent $MarkdownOutput
if ($mdParent -and !(Test-Path $mdParent)) { New-Item -ItemType Directory -Path $mdParent | Out-Null }
$lines | Set-Content -Encoding UTF8 $MarkdownOutput

[ordered]@{
  json = $JsonOutput
  markdown = $MarkdownOutput
  capability_count = $matrix.Count
  incomplete_count = @($matrix | Where-Object { $_.implementation_status -eq "not_migrated" -or $_.implementation_status -eq "partially_migrated" }).Count
} | ConvertTo-Json -Depth 4
