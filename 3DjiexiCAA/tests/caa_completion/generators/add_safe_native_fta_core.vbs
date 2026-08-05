Option Explicit

' Adds only the native FTA objects that were proven safe in this R21 session:
' DATUM_B, DATUM_C via CreateEvoluateDatum and GDT_FLATNESS via CreateToleranceWithoutDRF(3).

Dim fso, fixtureDir, path, catia, cfg, doc, part, annSet, annFactory, userSurfaces, changed
Set fso = CreateObject("Scripting.FileSystemObject")
If WScript.Arguments.Count = 1 And LCase(WScript.Arguments(0)) = "--syntax-check" Then
  WScript.Echo "[SYNTAX-OK] add_safe_native_fta_core.vbs"
  WScript.Quit 0
End If
If WScript.Arguments.Count <> 1 Then
  WScript.Echo "Usage: cscript //nologo add_safe_native_fta_core.vbs <fixture-directory>"
  WScript.Quit 2
End If

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
Set annFactory = annSet.AnnotationFactory
Set userSurfaces = part.UserSurfaces
changed = False

AddDatumOnTop "DATUM_B", "B", 20
AddDatumOnTop "DATUM_C", "C", 35
AddFlatnessOnTop

If changed Then doc.Save
doc.Close
catia.Quit
WScript.Echo "[DONE] safe native FTA core objects processed"
WScript.Quit 0

Sub AddDatumOnTop(ByVal objectName, ByVal label, ByVal x)
  If HasAnnotation(objectName) Then WScript.Echo "[SKIP] " & objectName: Exit Sub
  Dim us, ann, ds, e, d
  Set us = TopUserSurface()
  Err.Clear
  On Error Resume Next
  Set ann = annFactory.CreateEvoluateDatum(us, x, 5, 35, True)
  e = Err.Number: d = Err.Description
  On Error GoTo 0
  If e <> 0 Or ann Is Nothing Then WScript.Echo "[COM-ERROR] " & objectName & " CreateEvoluateDatum 0x" & Hex(e) & " " & d: Exit Sub
  Err.Clear
  On Error Resume Next
  ann.Name = objectName
  Set ds = ann.DatumSimple
  ds.Label = label
  ann.ModifyVisu
  e = Err.Number: d = Err.Description
  On Error GoTo 0
  If e <> 0 Then WScript.Echo "[COM-ERROR] " & objectName & " set label 0x" & Hex(e) & " " & d: Exit Sub
  doc.Save
  changed = True
  WScript.Echo "[ADDED] " & objectName & " nativeType=" & AnnType(ann)
End Sub

Sub AddFlatnessOnTop()
  If HasAnnotation("GDT_FLATNESS") Then WScript.Echo "[SKIP] GDT_FLATNESS": Exit Sub
  Dim us, ann, tz, e, d
  Set us = TopUserSurface()
  Err.Clear
  On Error Resume Next
  Set ann = annFactory.CreateToleranceWithoutDRF(3, us)
  e = Err.Number: d = Err.Description
  On Error GoTo 0
  If e <> 0 Or ann Is Nothing Then WScript.Echo "[COM-ERROR] GDT_FLATNESS CreateToleranceWithoutDRF(3) 0x" & Hex(e) & " " & d: Exit Sub
  If InStr(1, AnnType(ann), "FTA_Flatness", vbTextCompare) = 0 Then WScript.Echo "[BLOCKED] GDT_FLATNESS wrong native type " & AnnType(ann): Exit Sub
  Err.Clear
  On Error Resume Next
  ann.Name = "GDT_FLATNESS"
  Set tz = ann.ToleranceZone
  tz.Value = 0.08
  ann.ModifyVisu
  e = Err.Number: d = Err.Description
  On Error GoTo 0
  If e <> 0 Then WScript.Echo "[COM-ERROR] GDT_FLATNESS set value 0x" & Hex(e) & " " & d: Exit Sub
  doc.Save
  changed = True
  WScript.Echo "[ADDED] GDT_FLATNESS nativeType=" & AnnType(ann)
End Sub

Function TopUserSurface()
  Dim pad, ref
  Set pad = part.Bodies.Item(1).Shapes.Item("Pad_FTA_Carrier")
  Set ref = part.CreateReferenceFromBRepName("Face:(Brp:(Pad_FTA_Carrier;2);None:();Cf11:());WithTemporaryBody;WithoutBuildError;WithSelectingFeatureSupport;MFBRepVersion_CXR15)", pad)
  Set TopUserSurface = userSurfaces.Generate(ref)
End Function

Function HasAnnotation(ByVal objectName)
  Dim anns, i
  HasAnnotation = False
  Set anns = annSet.Annotations
  For i = 1 To anns.Count
    If LCase(SafeName(anns.Item(i))) = LCase(objectName) Then HasAnnotation = True: Exit Function
  Next
End Function

Function SafeName(ByVal obj)
  SafeName = ""
  Err.Clear
  On Error Resume Next
  SafeName = CStr(obj.Name)
  If Err.Number <> 0 Then SafeName = "": Err.Clear
  On Error GoTo 0
End Function

Function AnnType(ByVal ann)
  AnnType = TypeName(ann)
  Err.Clear
  On Error Resume Next
  AnnType = AnnType & "/Type=" & ann.Type & "/SuperType=" & ann.SuperType
  If Err.Number <> 0 Then Err.Clear
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
