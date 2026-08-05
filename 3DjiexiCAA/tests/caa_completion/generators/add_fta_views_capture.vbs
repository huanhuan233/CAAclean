Option Explicit

' Adds TPS views and a capture to fta_all_semantic_types.CATPart when R21 Automation permits it.

Dim fso, fixtureDir, path, catia, cfg, doc, part, annSet, changed
Set fso = CreateObject("Scripting.FileSystemObject")
If WScript.Arguments.Count = 1 And LCase(WScript.Arguments(0)) = "--syntax-check" Then
  WScript.Echo "[SYNTAX-OK] add_fta_views_capture.vbs"
  WScript.Quit 0
End If
If WScript.Arguments.Count <> 1 Then WScript.Echo "Usage: cscript //nologo add_fta_views_capture.vbs <fixture-directory>": WScript.Quit 2
fixtureDir = fso.GetAbsolutePathName(WScript.Arguments(0))
path = fso.BuildPath(fixtureDir, "fta_all_semantic_types.CATPart")
If Not fso.FileExists(path) Then WScript.Echo "[ERROR] Missing " & path: WScript.Quit 3

Set catia = CreateCatia()
catia.Visible = True
catia.DisplayFileAlerts = False
Set cfg = catia.SystemConfiguration
If cfg.Version <> 5 Or cfg.Release <> 21 Then Fatal "Expected CATIA V5R21, got " & RuntimeText(), 4
Set doc = catia.Documents.Open(path)
Set part = doc.Part
Set annSet = part.AnnotationSets.Item(1)
changed = False

AddView "VIEW_FRONT", part.OriginElements.PlaneYZ, 0
AddView "VIEW_TOP", part.OriginElements.PlaneXY, 1
AddCapture "CAPTURE_MACHINING"

If changed Then doc.Save
doc.Close
catia.Quit
WScript.Echo "[DONE] TPS views/capture processed"
WScript.Quit 0

Sub AddView(ByVal objectName, ByVal planeObj, ByVal viewType)
  If HasName(objectName) Then WScript.Echo "[SKIP] " & objectName: Exit Sub
  Dim factory, ref, view, e, d
  Set factory = annSet.TPSViewFactory
  Set ref = part.CreateReferenceFromObject(planeObj)
  Err.Clear
  On Error Resume Next
  Set view = factory.CreateView(ref, viewType)
  e = Err.Number: d = Err.Description
  On Error GoTo 0
  If e <> 0 Or view Is Nothing Then WScript.Echo "[COM-ERROR] " & objectName & " CreateView 0x" & Hex(e) & " " & d: Exit Sub
  Err.Clear
  On Error Resume Next
  view.Name = objectName
  e = Err.Number: d = Err.Description
  On Error GoTo 0
  If e <> 0 Then WScript.Echo "[COM-ERROR] " & objectName & " set Name 0x" & Hex(e) & " " & d: Exit Sub
  doc.Save
  changed = True
  WScript.Echo "[ADDED] " & objectName & " nativeType=" & TypeName(view)
End Sub

Sub AddCapture(ByVal objectName)
  If HasName(objectName) Then WScript.Echo "[SKIP] " & objectName: Exit Sub
  Dim factory, cap, e, d
  Set factory = annSet.CaptureFactory
  Err.Clear
  On Error Resume Next
  Set cap = factory.CreateCapture()
  e = Err.Number: d = Err.Description
  On Error GoTo 0
  If e <> 0 Or cap Is Nothing Then WScript.Echo "[COM-ERROR] " & objectName & " CreateCapture 0x" & Hex(e) & " " & d: Exit Sub
  Err.Clear
  On Error Resume Next
  cap.Name = objectName
  Set cap.Annotations = annSet.Annotations
  Set cap.TPSViews = annSet.TPSViews
  cap.Current = True
  e = Err.Number: d = Err.Description
  On Error GoTo 0
  If e <> 0 Then WScript.Echo "[COM-ERROR] " & objectName & " set capture properties 0x" & Hex(e) & " " & d: Exit Sub
  doc.Save
  changed = True
  WScript.Echo "[ADDED] " & objectName & " nativeType=" & TypeName(cap)
End Sub

Function HasName(ByVal objectName)
  Dim i, coll
  HasName = False
  Set coll = annSet.Annotations
  For i = 1 To coll.Count
    If LCase(SafeName(coll.Item(i))) = LCase(objectName) Then HasName = True: Exit Function
  Next
  Err.Clear
  On Error Resume Next
  Set coll = annSet.TPSViews
  For i = 1 To coll.Count
    If LCase(SafeName(coll.Item(i))) = LCase(objectName) Then HasName = True: Exit Function
  Next
  Set coll = annSet.Captures
  For i = 1 To coll.Count
    If LCase(SafeName(coll.Item(i))) = LCase(objectName) Then HasName = True: Exit Function
  Next
  Err.Clear
  On Error GoTo 0
End Function

Function SafeName(ByVal obj)
  SafeName = ""
  Err.Clear
  On Error Resume Next
  SafeName = CStr(obj.Name)
  If Err.Number <> 0 Then SafeName = "": Err.Clear
  On Error GoTo 0
End Function

Function CreateCatia()
  Err.Clear
  On Error Resume Next
  Set CreateCatia = CreateObject("CATIA.Application")
  Dim e, d: e = Err.Number: d = Err.Description
  On Error GoTo 0
  If e <> 0 Or CreateCatia Is Nothing Then WScript.Echo "[ERROR] Create CATIA.Application 0x" & Hex(e) & " " & d: WScript.Quit 9
End Function

Function RuntimeText(): RuntimeText = "V" & cfg.Version & "R" & cfg.Release & "SP" & cfg.ServicePack: End Function
Sub Fatal(ByVal message, ByVal code)
  WScript.Echo "[ERROR] " & message
  On Error Resume Next
  If Not doc Is Nothing Then doc.Close
  If Not catia Is Nothing Then catia.Quit
  WScript.Quit code
End Sub
