param(
  [string]$CaaPrereqRoot = "",
  [string]$OutputDir = ""
)

$ErrorActionPreference = "Stop"

function Resolve-DefaultPrereqRoot {
  if ($env:CAA_PREREQ_ROOT -and (Test-Path -LiteralPath $env:CAA_PREREQ_ROOT)) {
    return (Resolve-Path -LiteralPath $env:CAA_PREREQ_ROOT).Path
  }
  $candidate = Join-Path $PSScriptRoot "..\..\.caa_toolchain_links\catia21"
  if (Test-Path -LiteralPath $candidate) {
    return (Resolve-Path -LiteralPath $candidate).Path
  }
  throw "CAA_PREREQ_ROOT is required."
}

function JsonEscape([string]$Value) {
  if ($null -eq $Value) { return "" }
  $builder = New-Object System.Text.StringBuilder
  foreach ($ch in $Value.ToCharArray()) {
    switch ($ch) {
      '"'  { [void]$builder.Append('\"') }
      '\'  { [void]$builder.Append('\\') }
      "`b" { [void]$builder.Append('\b') }
      "`f" { [void]$builder.Append('\f') }
      "`n" { [void]$builder.Append('\n') }
      "`r" { [void]$builder.Append('\r') }
      "`t" { [void]$builder.Append('\t') }
      default {
        if ([int][char]$ch -lt 32) {
          [void]$builder.Append(('\u{0:x4}' -f [int][char]$ch))
        } else {
          [void]$builder.Append($ch)
        }
      }
    }
  }
  return $builder.ToString()
}

function Quote([string]$Value) {
  return '"' + (JsonEscape $Value) + '"'
}

if (-not $CaaPrereqRoot) {
  $CaaPrereqRoot = Resolve-DefaultPrereqRoot
} else {
  $CaaPrereqRoot = (Resolve-Path -LiteralPath $CaaPrereqRoot).Path
}

if (-not $OutputDir) {
  $OutputDir = Join-Path $PSScriptRoot "..\catalog"
}
$OutputDir = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($OutputDir)
if (-not (Test-Path -LiteralPath $OutputDir)) {
  New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
}

$frameworks = @()
$headers = @()

Get-ChildItem -LiteralPath $CaaPrereqRoot -Directory |
  Where-Object { $_.Name -ne "CAADoc" -and (Test-Path -LiteralPath (Join-Path $_.FullName "PublicInterfaces")) } |
  Sort-Object Name |
  ForEach-Object {
    $framework = $_.Name
    $publicDir = Join-Path $_.FullName "PublicInterfaces"
    $frameworkHeaders = @(Get-ChildItem -LiteralPath $publicDir -File -Include *.h,*.hpp -Recurse | Sort-Object FullName)
    $frameworks += [pscustomobject]@{
      framework = $framework
      root = $_.FullName.Substring($CaaPrereqRoot.Length).TrimStart('\')
      status = "indexed"
      public_headers = @($frameworkHeaders | ForEach-Object { $_.Name })
    }
    foreach ($header in $frameworkHeaders) {
      $headers += [pscustomobject]@{
        header = $header.Name
        framework = $framework
        relative_path = $header.FullName.Substring($CaaPrereqRoot.Length).TrimStart('\')
        status = "indexed"
      }
    }
  }

$apiPath = Join-Path $OutputDir "r21_api_catalog.json"
$fwPath = Join-Path $OutputDir "r21_framework_catalog.json"

$api = New-Object System.Text.StringBuilder
[void]$api.AppendLine("{")
[void]$api.AppendLine('  "schema_version": "r21_api_catalog_v1",')
[void]$api.AppendLine('  "source": ' + (Quote $CaaPrereqRoot) + ',')
[void]$api.AppendLine('  "status_chain": ["indexed", "header_verified", "compile_verified", "runtime_verified", "extractor_implemented", "fixture_verified", "reconstruction_verified"],')
[void]$api.AppendLine('  "headers": [')
for ($i = 0; $i -lt $headers.Count; ++$i) {
  $h = $headers[$i]
  $comma = if ($i -lt $headers.Count - 1) { "," } else { "" }
  [void]$api.AppendLine(('    {{"header": {0}, "framework": {1}, "relative_path": {2}, "status": "indexed"}}{3}' -f (Quote $h.header), (Quote $h.framework), (Quote $h.relative_path), $comma))
}
[void]$api.AppendLine("  ]")
[void]$api.AppendLine("}")
[System.IO.File]::WriteAllText($apiPath, $api.ToString(), [System.Text.Encoding]::UTF8)

$fw = New-Object System.Text.StringBuilder
[void]$fw.AppendLine("{")
[void]$fw.AppendLine('  "schema_version": "r21_framework_catalog_v1",')
[void]$fw.AppendLine('  "source": ' + (Quote $CaaPrereqRoot) + ',')
[void]$fw.AppendLine('  "frameworks": [')
for ($i = 0; $i -lt $frameworks.Count; ++$i) {
  $f = $frameworks[$i]
  $comma = if ($i -lt $frameworks.Count - 1) { "," } else { "" }
  [void]$fw.Append(('    {{"framework": {0}, "root": {1}, "status": "indexed", "public_headers": [' -f (Quote $f.framework), (Quote $f.root)))
  for ($j = 0; $j -lt $f.public_headers.Count; ++$j) {
    if ($j -gt 0) { [void]$fw.Append(", ") }
    [void]$fw.Append((Quote $f.public_headers[$j]))
  }
  [void]$fw.AppendLine(("]}}{0}" -f $comma))
}
[void]$fw.AppendLine("  ]")
[void]$fw.AppendLine("}")
[System.IO.File]::WriteAllText($fwPath, $fw.ToString(), [System.Text.Encoding]::UTF8)

Write-Host "Wrote $apiPath"
Write-Host "Wrote $fwPath"
Write-Host "Indexed headers: $($headers.Count)"
Write-Host "Indexed frameworks: $($frameworks.Count)"
