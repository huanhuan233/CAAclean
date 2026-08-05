Option Explicit

' Independently reopens every generated CATPart/CATProduct and records native evidence.
' The JSONL is evidence only; the parser never reads it.

Dim fso, fixtureDir, reportPath, report, catia, cfg, folder, file, failures
Set fso = CreateObject("Scripting.FileSystemObject")
If WScript.Arguments.Count <> 1 Then
  WScript.Echo "Usage: cscript //nologo verify_real_fixtures.vbs <fixture-directory>"
  WScript.Quit 2
End If
fixtureDir = fso.GetAbsolutePathName(WScript.Arguments(0))
reportPath = fso.BuildPath(fixtureDir, "fixture_reopen_evidence.jsonl")
Set report = fso.CreateTextFile(reportPath, True, False)
failures = 0

On Error Resume Next
Set catia = CreateObject("CATIA.Application")
If Err.Number <> 0 Then Fatal "Create CATIA.Application", 3
catia.Visible = False: catia.DisplayFileAlerts = False
Set cfg = catia.SystemConfiguration
If Err.Number <> 0 Or cfg.Version <> 5 Or cfg.Release <> 21 Then Fatal "Expected CATIA V5R21", 4

Set folder = fso.GetFolder(fixtureDir)
For Each file In folder.Files
  If LCase(fso.GetExtensionName(file.Name)) = "catpart" Then VerifyPart file.Path
  If LCase(fso.GetExtensionName(file.Name)) = "catproduct" Then VerifyProduct file.Path
Next

report.Close: catia.Quit
If failures > 0 Then
  WScript.Echo "[FAIL] reopen failures=" & failures
  WScript.Quit 1
End If
WScript.Echo "[PASS] all generated CATIA files reopened; evidence=" & reportPath
WScript.Quit 0

Sub VerifyPart(ByVal path)
  On Error Resume Next
  Dim doc, part, bodyCount, shapeCount, annotationCount, volume, errorText, i, j, body, shapeNames
  Err.Clear
  Set doc = catia.Documents.Open(path)
  If Err.Number <> 0 Then
    errorText = Err.Description: Err.Clear: failures = failures + 1
    report.WriteLine "{""file"":""" & J(fso.GetFileName(path)) & """,""kind"":""CATPart"",""status"":""failed"",""error"":""" & J(errorText) & """}"
    Exit Sub
  End If
  Set part = doc.Part
  bodyCount = part.Bodies.Count
  shapeCount = 0: shapeNames = "["
  For i = 1 To bodyCount
    Set body = part.Bodies.Item(i)
    For j = 1 To body.Shapes.Count
      If shapeCount > 0 Then shapeNames = shapeNames & ","
      shapeNames = shapeNames & "{""name"":""" & J(body.Shapes.Item(j).Name) & """,""automation_type"":""" & J(TypeName(body.Shapes.Item(j))) & """,""up_to_date"":" & BoolText(part.IsUpToDate(body.Shapes.Item(j))) & "}"
      shapeCount = shapeCount + 1
    Next
  Next
  shapeNames = shapeNames & "]"
  Err.Clear
  annotationCount = part.AnnotationSets.Count
  If Err.Number <> 0 Then annotationCount = -1: Err.Clear
  volume = doc.Product.Analyze.Volume
  If Err.Number <> 0 Then volume = -1: Err.Clear
  report.WriteLine "{""file"":""" & J(fso.GetFileName(path)) & """,""kind"":""CATPart"",""status"":""verified"",""runtime"":""" & RuntimeText() & """,""body_count"":" & bodyCount & ",""shape_count"":" & shapeCount & ",""annotation_set_count"":" & annotationCount & ",""volume_m3"":" & NumberText(volume) & ",""shapes"":" & shapeNames & "}"
  doc.Close
  WScript.Echo "[VERIFIED] " & fso.GetFileName(path) & " shapes=" & shapeCount & " annotations=" & annotationCount
End Sub

Sub VerifyProduct(ByVal path)
  On Error Resume Next
  Dim doc, root, children, i, child, matrix(11), items, errorText
  Err.Clear
  Set doc = catia.Documents.Open(path)
  If Err.Number <> 0 Then
    errorText = Err.Description: Err.Clear: failures = failures + 1
    report.WriteLine "{""file"":""" & J(fso.GetFileName(path)) & """,""kind"":""CATProduct"",""status"":""failed"",""error"":""" & J(errorText) & """}"
    Exit Sub
  End If
  Set root = doc.Product: Set children = root.Products: items = "["
  For i = 1 To children.Count
    Set child = children.Item(i)
    If i > 1 Then items = items & ","
    Err.Clear
    child.Position.GetComponents matrix
    If Err.Number <> 0 Then Err.Clear: IdentityMatrix matrix
    items = items & "{""name"":""" & J(child.Name) & """,""part_number"":""" & J(child.PartNumber) & """,""matrix_3x4"":" & MatrixText(matrix) & "}"
  Next
  items = items & "]"
  report.WriteLine "{""file"":""" & J(fso.GetFileName(path)) & """,""kind"":""CATProduct"",""status"":""verified"",""runtime"":""" & RuntimeText() & """,""root_part_number"":""" & J(root.PartNumber) & """,""child_count"":" & children.Count & ",""children"":" & items & "}"
  doc.Close
  WScript.Echo "[VERIFIED] " & fso.GetFileName(path) & " children=" & children.Count
End Sub

Sub IdentityMatrix(ByRef m)
  m(0)=1: m(1)=0: m(2)=0: m(3)=0: m(4)=1: m(5)=0
  m(6)=0: m(7)=0: m(8)=1: m(9)=0: m(10)=0: m(11)=0
End Sub

Function MatrixText(ByRef m)
  Dim i, text: text = "["
  For i = 0 To 11
    If i > 0 Then text = text & ","
    text = text & NumberText(m(i))
  Next
  MatrixText = text & "]"
End Function

Function J(ByVal value)
  Dim text: text = CStr(value)
  text = Replace(text, Chr(92), Chr(92) & Chr(92))
  text = Replace(text, Chr(34), Chr(92) & Chr(34))
  text = Replace(text, vbCr, Chr(92) & "r")
  text = Replace(text, vbLf, Chr(92) & "n")
  J = text
End Function
Function NumberText(ByVal value): NumberText = Replace(CStr(value), ",", "."): End Function
Function BoolText(ByVal value): If value Then BoolText = "true" Else BoolText = "false": End If: End Function
Function RuntimeText(): RuntimeText = "V" & cfg.Version & "R" & cfg.Release & "SP" & cfg.ServicePack: End Function

Sub Fatal(ByVal message, ByVal code)
  On Error Resume Next
  WScript.Echo "[ERROR] " & message & " 0x" & Hex(Err.Number) & " " & Err.Description
  report.Close: If Not catia Is Nothing Then catia.Quit
  WScript.Quit code
End Sub
