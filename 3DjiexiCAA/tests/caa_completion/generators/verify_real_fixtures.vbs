Option Explicit

' Independently reopens every generated CATPart/CATProduct and records native evidence.
' The JSONL is evidence only; the parser never reads it.

Dim fso, fixtureDir, reportPath, report, catia, cfg, folder, file, failures
Set fso = CreateObject("Scripting.FileSystemObject")
If WScript.Arguments.Count = 1 And LCase(WScript.Arguments(0)) = "--syntax-check" Then
  WScript.Echo "[SYNTAX-OK] verify_real_fixtures.vbs"
  WScript.Quit 0
End If
If WScript.Arguments.Count <> 1 Then
  WScript.Echo "Usage: cscript //nologo verify_real_fixtures.vbs <fixture-directory>"
  WScript.Quit 2
End If
fixtureDir = fso.GetAbsolutePathName(WScript.Arguments(0))
reportPath = fso.BuildPath(fixtureDir, "fixture_reopen_evidence.jsonl")
Set report = fso.CreateTextFile(reportPath, True, False)
failures = 0

Set catia = CreateCatia()
catia.Visible = False
catia.DisplayFileAlerts = False
Set cfg = catia.SystemConfiguration
If cfg.Version <> 5 Or cfg.Release <> 21 Then Fatal "Expected CATIA V5R21, got " & RuntimeText(), 4

Set folder = fso.GetFolder(fixtureDir)
For Each file In folder.Files
  If LCase(fso.GetExtensionName(file.Name)) = "catpart" Then VerifyPart file.Path
  If LCase(fso.GetExtensionName(file.Name)) = "catproduct" Then VerifyProduct file.Path
Next

report.Close
catia.Quit
If failures > 0 Then
  WScript.Echo "[FAIL] reopen failures=" & failures
  WScript.Quit 1
End If
WScript.Echo "[PASS] all generated CATIA files reopened; evidence=" & reportPath
WScript.Quit 0

Sub VerifyPart(ByVal path)
  Dim doc, part, bodyCount, shapeCount, annotationCount, volume, errorText, i, j, body, shapeNames, axisCount
  Err.Clear
  On Error Resume Next
  Set doc = catia.Documents.Open(path)
  If Err.Number <> 0 Then
    errorText = Err.Description: Err.Clear: On Error GoTo 0
    failures = failures + 1
    report.WriteLine "{""file"":""" & JsonText(fso.GetFileName(path)) & """,""kind"":""CATPart"",""status"":""failed"",""error"":""" & JsonText(errorText) & """}"
    Exit Sub
  End If
  On Error GoTo 0
  Set part = doc.Part
  bodyCount = part.Bodies.Count
  shapeCount = 0: shapeNames = "["
  For i = 1 To bodyCount
    Set body = part.Bodies.Item(i)
    For j = 1 To body.Shapes.Count
      If shapeCount > 0 Then shapeNames = shapeNames & ","
      shapeNames = shapeNames & "{""body"":""" & JsonText(body.Name) & """,""name"":""" & JsonText(body.Shapes.Item(j).Name) & """,""automation_type"":""" & JsonText(TypeName(body.Shapes.Item(j))) & """,""up_to_date"":" & BoolText(part.IsUpToDate(body.Shapes.Item(j))) & "}"
      shapeCount = shapeCount + 1
    Next
  Next
  shapeNames = shapeNames & "]"
  Err.Clear
  On Error Resume Next
  annotationCount = part.AnnotationSets.Count
  If Err.Number <> 0 Then annotationCount = -1: Err.Clear
  axisCount = part.AxisSystems.Count
  If Err.Number <> 0 Then axisCount = -1: Err.Clear
  volume = doc.Product.Analyze.Volume
  If Err.Number <> 0 Then volume = -1: Err.Clear
  On Error GoTo 0
  report.WriteLine "{""file"":""" & JsonText(fso.GetFileName(path)) & """,""kind"":""CATPart"",""status"":""verified"",""runtime"":""" & RuntimeText() & """,""body_count"":" & bodyCount & ",""shape_count"":" & shapeCount & ",""axis_system_count"":" & axisCount & ",""annotation_set_count"":" & annotationCount & ",""volume_m3"":" & NumberText(volume) & ",""shapes"":" & shapeNames & "}"
  doc.Close
  WScript.Echo "[VERIFIED] " & fso.GetFileName(path) & " shapes=" & shapeCount & " annotations=" & annotationCount
End Sub

Sub VerifyProduct(ByVal path)
  Dim doc, root, children, childCount, nodes, errorText
  Err.Clear
  On Error Resume Next
  Set doc = catia.Documents.Open(path)
  If Err.Number <> 0 Then
    errorText = Err.Description: Err.Clear: On Error GoTo 0
    failures = failures + 1
    report.WriteLine "{""file"":""" & JsonText(fso.GetFileName(path)) & """,""kind"":""CATProduct"",""status"":""failed"",""error"":""" & JsonText(errorText) & """}"
    Exit Sub
  End If
  On Error GoTo 0
  Set root = doc.Product
  Set children = root.Products
  childCount = children.Count
  nodes = "["
  WalkProduct root, "", nodes
  nodes = nodes & "]"
  report.WriteLine "{""file"":""" & JsonText(fso.GetFileName(path)) & """,""kind"":""CATProduct"",""status"":""verified"",""runtime"":""" & RuntimeText() & """,""root_part_number"":""" & JsonText(root.PartNumber) & """,""child_count"":" & childCount & ",""nodes"":" & nodes & "}"
  doc.Close
  WScript.Echo "[VERIFIED] " & fso.GetFileName(path) & " root_children=" & childCount
End Sub

Sub WalkProduct(ByVal product, ByVal prefix, ByRef nodes)
  Dim i, child, matrix(11), pathText, refPn, refName, comma
  For i = 1 To product.Products.Count
    Set child = product.Products.Item(i)
    pathText = prefix & "/" & child.Name
    If Len(nodes) > 1 Then comma = "," Else comma = ""
    Err.Clear
    On Error Resume Next
    child.Position.GetComponents matrix
    If Err.Number <> 0 Then Err.Clear: IdentityMatrix matrix
    refPn = "": refName = ""
    If Not child.ReferenceProduct Is Nothing Then
      refPn = child.ReferenceProduct.PartNumber
      refName = child.ReferenceProduct.Name
    End If
    On Error GoTo 0
    nodes = nodes & comma & "{""path"":""" & JsonText(pathText) & """,""name"":""" & JsonText(child.Name) & """,""part_number"":""" & JsonText(child.PartNumber) & """,""reference_part_number"":""" & JsonText(refPn) & """,""reference_name"":""" & JsonText(refName) & """,""child_count"":" & child.Products.Count & ",""matrix_3x4"":" & MatrixText(matrix) & "}"
    WalkProduct child, pathText, nodes
  Next
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

Function JsonText(ByVal value)
  Dim text: text = CStr(value)
  text = Replace(text, Chr(92), Chr(92) & Chr(92))
  text = Replace(text, Chr(34), Chr(92) & Chr(34))
  text = Replace(text, vbCr, Chr(92) & "r")
  text = Replace(text, vbLf, Chr(92) & "n")
  JsonText = text
End Function

Function NumberText(ByVal value): NumberText = Replace(CStr(value), ",", "."): End Function
Function BoolText(ByVal value): If value Then BoolText = "true" Else BoolText = "false": End If: End Function
Function RuntimeText(): RuntimeText = "V" & cfg.Version & "R" & cfg.Release & "SP" & cfg.ServicePack: End Function

Function CreateCatia()
  Err.Clear
  On Error Resume Next
  Set CreateCatia = CreateObject("CATIA.Application")
  Dim e, d: e = Err.Number: d = Err.Description
  On Error GoTo 0
  If e <> 0 Or CreateCatia Is Nothing Then
    WScript.Echo "[ERROR] Create CATIA.Application 0x" & Hex(e) & " " & d
    WScript.Quit 3
  End If
End Function

Sub Fatal(ByVal message, ByVal code)
  WScript.Echo "[ERROR] " & message
  On Error Resume Next
  If Not report Is Nothing Then report.Close
  If Not catia Is Nothing Then catia.Quit
  WScript.Quit code
End Sub
