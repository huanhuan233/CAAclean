Option Explicit

Dim fso, inputPath, outputPath, reportPath, reportFile
Dim catia, document, part, body, configuration, shape, index

Set fso = CreateObject("Scripting.FileSystemObject")
Set catia = Nothing
Set document = Nothing
Set reportFile = Nothing

If WScript.Arguments.Count <> 3 Then
  WScript.Echo "STEP_EXPORT_ARGUMENTS_INVALID"
  WScript.Quit 2
End If

inputPath = fso.GetAbsolutePathName(WScript.Arguments(0))
outputPath = fso.GetAbsolutePathName(WScript.Arguments(1))
reportPath = fso.GetAbsolutePathName(WScript.Arguments(2))

On Error Resume Next
Set reportFile = fso.CreateTextFile(reportPath, True, False)
RequireSuccess "create_report"

' 用途：创建本脚本独占的 CATIA 实例，导出结束后无论成功失败都负责关闭。
Set catia = CreateObject("CATIA.Application")
RequireSuccess "create_catia_application"
catia.Visible = False
RequireSuccess "set_catia_visible"
catia.DisplayFileAlerts = False
RequireSuccess "set_catia_file_alerts"
Set configuration = catia.SystemConfiguration
RequireSuccess "read_catia_runtime"
WriteProperty "runtime.version", CStr(configuration.Version)
WriteProperty "runtime.release", CStr(configuration.Release)
WriteProperty "runtime.service_pack", CStr(configuration.ServicePack)

' 用途：只读打开 CATPart 并记录导出前的实际更新状态，不调用更新或保存接口。
Set document = catia.Documents.Open(inputPath)
RequireSuccess "open_catpart"
Set part = document.Part
RequireSuccess "read_part"
Set body = part.MainBody
RequireSuccess "read_main_body"
For index = 1 To body.Shapes.Count
  Set shape = body.Shapes.Item(index)
  WriteProperty "state.before." & shape.Name, UpdateState(part, shape)
Next

' 用途：调用 R21 CATIADocument Automation 的真实 STEP 导出入口。
document.ExportData outputPath, "stp"
RequireSuccess "export_step"
If Not fso.FileExists(outputPath) Then Fail "export_output_missing", 4

' 用途：再次采样同一历史对象，证明导出过程没有主动改变更新状态。
For index = 1 To body.Shapes.Count
  Set shape = body.Shapes.Item(index)
  WriteProperty "state.after." & shape.Name, UpdateState(part, shape)
Next

document.Close
RequireSuccess "close_catpart"
Set document = Nothing
reportFile.Close
Set reportFile = Nothing
catia.Quit
RequireSuccess "quit_catia"
Set catia = Nothing
WScript.Echo "STEP_EXPORT_AUTOMATION_OK"
WScript.Quit 0

' 用途：通过 Part.IsUpToDate 返回真实设计状态，接口异常时明确标记 unavailable。
Function UpdateState(ByVal currentPart, ByVal feature)
  On Error Resume Next
  Err.Clear
  If currentPart.IsUpToDate(feature) Then
    If Err.Number = 0 Then
      UpdateState = "up_to_date"
    Else
      Err.Clear
      UpdateState = "unavailable"
    End If
  Else
    If Err.Number = 0 Then
      UpdateState = "not_up_to_date"
    Else
      Err.Clear
      UpdateState = "unavailable"
    End If
  End If
End Function

' 用途：写入不含本机路径的键值证据，最终 JSON 由 PowerShell 编排层生成。
Sub WriteProperty(ByVal key, ByVal value)
  On Error Resume Next
  reportFile.WriteLine key & "=" & value
  RequireSuccess "write_report_property"
End Sub

' 用途：把当前 Automation 错误转换为带阶段名的非零退出，禁止静默降级。
Sub RequireSuccess(ByVal stage)
  On Error Resume Next
  If Err.Number <> 0 Then
    Dim message
    message = stage & "|0x" & Hex(Err.Number) & "|" & Err.Description
    Err.Clear
    Fail message, 5
  End If
  Err.Clear
End Sub

' 用途：失败路径只关闭不保存，并退出本脚本创建的 CATIA 实例。
Sub Fail(ByVal message, ByVal code)
  On Error Resume Next
  WScript.Echo "STEP_EXPORT_AUTOMATION_FAILED " & message
  Err.Clear
  If Not document Is Nothing Then document.Close
  Err.Clear
  If Not reportFile Is Nothing Then reportFile.Close
  Err.Clear
  If Not catia Is Nothing Then catia.Quit
  On Error GoTo 0
  WScript.Quit code
End Sub
