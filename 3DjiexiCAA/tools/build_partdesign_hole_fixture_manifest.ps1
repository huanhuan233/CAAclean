param(
    [Parameter(Mandatory = $true)]
    [string]$FixtureDirectory,

    [Parameter(Mandatory = $true)]
    [string]$VerificationReport
)

$ErrorActionPreference = 'Stop'

# Reads the verifier's deliberately simple key=value evidence file.
function Read-VerificationProperties {
    param([string]$Path)

    $properties = @{}
    foreach ($line in Get-Content -LiteralPath $Path -Encoding Default) {
        if ([string]::IsNullOrWhiteSpace($line)) { continue }
        $separator = $line.IndexOf('=')
        if ($separator -lt 1) { throw "Invalid verification property: $line" }
        $properties[$line.Substring(0, $separator)] = $line.Substring($separator + 1)
    }
    return $properties
}

# Returns file metadata only after the final CATIA save and independent reopen verification.
function Get-FixtureFileRecord {
    param([string]$Path)

    $item = Get-Item -LiteralPath $Path
    return @{
        size_bytes = [int64]$item.Length
        sha256 = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
    }
}

$fixtureRoot = (Resolve-Path -LiteralPath $FixtureDirectory).Path
$report = Read-VerificationProperties -Path $VerificationReport
$updatedPath = Join-Path $fixtureRoot 'partdesign_holes_updated.CATPart'
$stalePath = Join-Path $fixtureRoot 'partdesign_holes_stale.CATPart'
$updatedFile = Get-FixtureFileRecord -Path $updatedPath
$staleFile = Get-FixtureFileRecord -Path $stalePath

if ([int]$report['runtime.release'] -ne 21) { throw 'Verification did not run under CATIA R21.' }
if ([int]$report['updated.pad_count'] -lt 1) { throw 'Verified native Pad count is below the fixture contract.' }
if ([int]$report['updated.pocket_count'] -lt 1) { throw 'Verified native Pocket count is below the fixture contract.' }
if ([int]$report['updated.hole_count'] -lt 5) { throw 'Verified native Hole count is below the fixture contract.' }
if ($report['updated.all_up_to_date'] -ne 'true') { throw 'Updated fixture is not fully up-to-date.' }
if ($report['updated.cooling_port_native_hole'] -ne 'true') { throw 'CoolingPort_A was not verified as a native Hole.' }
if ($report['updated.pocket_rejected_as_hole'] -ne 'true') { throw 'Pocket_Control did not pass the negative Hole check.' }
if ([int]$report['stale.object_count'] -lt 1) { throw 'Stale fixture has no verified stale object.' }

$manifest = [ordered]@{
    schema_version = 'catia_r21_native_fixture_v1'
    generated_by = 'CATIA V5R21 Automation: generate_partdesign_hole_fixtures.vbs'
    generated_utc = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    catia_runtime = [ordered]@{
        release = "V5R$($report['runtime.release'])"
        service_pack = "SP$($report['runtime.service_pack'])"
        hotfix = 'unknown'
        value_source = $report['runtime.value_source'] + '; hotfix is not exposed by the verified Automation interface'
    }
    fixtures = @(
        [ordered]@{
            file_name = 'partdesign_holes_updated.CATPart'
            size_bytes = $updatedFile.size_bytes
            sha256 = $updatedFile.sha256
            expected_document_state = 'up_to_date'
            expected_native_features = [ordered]@{
                pad_min_count = 1
                pocket_min_count = 1
                hole_min_count = 5
                renamed_hole_name = 'CoolingPort_A'
                blind_hole = $true
                through_hole = $true
                counterbore_or_countersink_hole = $true
                threaded_hole = $true
            }
            verified_native_features = [ordered]@{
                pad_count = [int]$report['updated.pad_count']
                pocket_count = [int]$report['updated.pocket_count']
                hole_count = [int]$report['updated.hole_count']
                cooling_port_native_hole = [bool]::Parse($report['updated.cooling_port_native_hole'])
                pocket_rejected_as_hole = [bool]::Parse($report['updated.pocket_rejected_as_hole'])
                solid_volume_mm3 = [double]::Parse($report['updated.solid_volume_mm3'], [Globalization.CultureInfo]::InvariantCulture)
                status_source = 'Part.IsUpToDate'
            }
        },
        [ordered]@{
            file_name = 'partdesign_holes_stale.CATPart'
            size_bytes = $staleFile.size_bytes
            sha256 = $staleFile.sha256
            expected_document_state = 'not_up_to_date'
            expected_stale_object_min_count = 1
            verified_stale_object_count = [int]$report['stale.object_count']
            verified_stale_objects = @($report['stale.objects'].Split(';'))
            status_source = $report['stale.status_source']
        }
    )
}

$manifestPath = Join-Path $fixtureRoot 'fixtures_manifest.json'
$json = $manifest | ConvertTo-Json -Depth 8
[IO.File]::WriteAllText($manifestPath, $json + [Environment]::NewLine, (New-Object Text.UTF8Encoding($false)))
Write-Output "[MANIFEST] $manifestPath"
