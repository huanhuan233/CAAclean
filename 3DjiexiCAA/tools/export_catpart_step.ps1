param(
    [Parameter(Mandatory = $true)][string]$InputCatPart,
    [Parameter(Mandatory = $true)][string]$OutputStep,
    [string]$ReportPath = ""
)

$ErrorActionPreference = "Stop"
$source = (Resolve-Path -LiteralPath $InputCatPart).Path
$destination = [System.IO.Path]::GetFullPath($OutputStep)
if ([string]::IsNullOrWhiteSpace($ReportPath)) {
    $ReportPath = "$destination.export.json"
}
$report = [System.IO.Path]::GetFullPath($ReportPath)
$automationScript = Join-Path $PSScriptRoot "export_catpart_step.vbs"
$temporaryEvidence = Join-Path ([System.IO.Path]::GetTempPath()) (
    "catia-step-export-{0}.txt" -f [Guid]::NewGuid().ToString("N")
)
$temporaryAutomation = Join-Path ([System.IO.Path]::GetTempPath()) (
    "catia-step-export-{0}.vbs" -f [Guid]::NewGuid().ToString("N")
)
$succeeded = $false

# 用途：把 VBScript 的键值证据拆成普通字典，避免日志和命令行传递超长 JSON。
function Read-AutomationEvidence([string]$path) {
    $values = [ordered]@{}
    foreach ($line in Get-Content -LiteralPath $path) {
        $separator = $line.IndexOf("=")
        if ($separator -gt 0) {
            $values[$line.Substring(0, $separator)] = $line.Substring($separator + 1)
        }
    }
    return $values
}

try {
    if ([System.IO.Path]::GetExtension($source).ToLowerInvariant() -notin @(".catpart", ".catproduct")) {
        throw "STEP_EXPORT_INPUT_TYPE_INVALID：输入必须是 CATPart 或 CATProduct"
    }
    if (Test-Path -LiteralPath $destination) {
        throw "STEP_EXPORT_OUTPUT_EXISTS：拒绝覆盖已有 STEP"
    }
    foreach ($directory in @((Split-Path -Parent $destination), (Split-Path -Parent $report))) {
        if (-not (Test-Path -LiteralPath $directory)) {
            New-Item -ItemType Directory -Path $directory | Out-Null
        }
    }

    # 导出执行交给已在本机 R21 验证过的 WSH Automation；编排层只负责追溯和发布。
    $sourceHashBefore = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant()
    # WSH R21 不接受 UTF-8 脚本；运行时生成 UTF-16 临时副本，以便源码仍能保留中文注释。
    $automationText = Get-Content -Raw -Encoding UTF8 -LiteralPath $automationScript
    [System.IO.File]::WriteAllText($temporaryAutomation, $automationText, [System.Text.Encoding]::Unicode)
    & cscript.exe //nologo $temporaryAutomation $source $destination $temporaryEvidence
    if ($LASTEXITCODE -ne 0) {
        throw "STEP_EXPORT_AUTOMATION_FAILED：退出码 $LASTEXITCODE"
    }
    if (-not (Test-Path -LiteralPath $destination)) {
        throw "STEP_EXPORT_OUTPUT_MISSING：CATIA 未生成目标 STEP"
    }
    $sourceHashAfter = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($sourceHashBefore -ne $sourceHashAfter) {
        throw "STEP_EXPORT_SOURCE_CHANGED：导出前后 CATPart 哈希不同"
    }
    $evidence = Read-AutomationEvidence $temporaryEvidence
    $statesBefore = [ordered]@{}
    $statesAfter = [ordered]@{}
    foreach ($key in $evidence.Keys) {
        if ($key.StartsWith("state.before.")) {
            $statesBefore[$key.Substring(13)] = $evidence[$key]
        }
        elseif ($key.StartsWith("state.after.")) {
            $statesAfter[$key.Substring(12)] = $evidence[$key]
        }
    }
    if (($statesBefore | ConvertTo-Json -Compress) -ne ($statesAfter | ConvertTo-Json -Compress)) {
        throw "STEP_EXPORT_UPDATE_STATE_CHANGED：导出前后历史对象状态不同"
    }

    $result = [ordered]@{
        schema_version = "catia_step_export_v1"
        exporter = "CATIADocument.ExportData"
        format = "stp"
        source = [ordered]@{
            file_name = [System.IO.Path]::GetFileName($source)
            sha256_before = $sourceHashBefore
            sha256_after = $sourceHashAfter
            absolute_path_included = $false
        }
        output = [ordered]@{
            file_name = [System.IO.Path]::GetFileName($destination)
            size_bytes = (Get-Item -LiteralPath $destination).Length
            sha256 = (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant()
            absolute_path_included = $false
        }
        catia_runtime = [ordered]@{
            version = $evidence["runtime.version"]
            release = $evidence["runtime.release"]
            service_pack = $evidence["runtime.service_pack"]
            value_source = "CATIA.SystemConfiguration"
        }
        update_states_before = $statesBefore
        update_states_after = $statesAfter
        source_unchanged = $true
    }
    $utf8WithoutBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText(
        $report,
        (($result | ConvertTo-Json -Depth 8) + "`n"),
        $utf8WithoutBom
    )
    $succeeded = $true
    Write-Host "[STEP_EXPORT_OK] $([System.IO.Path]::GetFileName($destination))"
    exit 0
}
catch {
    Write-Error $_.Exception.Message
    exit 1
}
finally {
    if (Test-Path -LiteralPath $temporaryEvidence) {
        Remove-Item -LiteralPath $temporaryEvidence -Force
    }
    if (Test-Path -LiteralPath $temporaryAutomation) {
        Remove-Item -LiteralPath $temporaryAutomation -Force
    }
    if (-not $succeeded -and (Test-Path -LiteralPath $destination)) {
        Remove-Item -LiteralPath $destination -Force
    }
    # Automation 脚本负责关闭自身文档和应用；这里不按进程出现时间强杀 CNEXT，避免误伤用户并发会话。
}
