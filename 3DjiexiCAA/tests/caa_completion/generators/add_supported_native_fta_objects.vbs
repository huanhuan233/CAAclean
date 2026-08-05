Option Explicit

' Adds every native FTA object that was proven scriptable in CATIA V5R21SP0.
' It does not create placeholder Parameters/Properties and does not mislabel one native
' type as another. Unsupported dimensions and position tolerance are logged as blocked.

Dim fso, fixtureDir, path, catia, cfg, doc, part, annSet, annFactory, userSurfaces
Dim logText, changed
Set fso = CreateObject("Scripting.FileSystemObject")
If WScript.Arguments.Count = 1 And LCase(WScript.Arguments(0)) = "--syntax-check" Then
  WScript.Echo "[SYNTAX-OK] add_supported_native_fta_objects.vbs"
  WScript.Quit 0
End If
If WScript.Arguments.Count <> 1 Then
  WScript.Echo "Usage: cscript //nologo add_supported_native_fta_objects.vbs <fixture-directory>"
  WScript.Quit 2
End If

fixtureDir = fso.GetAbsolutePathName(WScript.Arguments(0))
path = fso.BuildPath(fixtureDir, "fta_all_semantic_types.CATPart")
If Not fso.FileExists(path) Then
  WScript.Echo "[ERROR] Missing formal FTA file " & path
  WScript.Quit 3
End If

Set catia = CreateCatia()
catia.Visible = True
catia.DisplayFileAlerts = False
Set cfg = catia.SystemConfiguration
If cfg.Version <> 5 Or cfg.Release <> 21 Then Fatal "Expected CATIA V5R21, got " & RuntimeText(), 4

Set doc = OpenDocument(path)
Set part = doc.Part
Set annSet = part.AnnotationSets.Item(1)
Set annFactory = annSet.AnnotationFactory
Set userSurfaces = part.UserSurfaces
changed = False

AddDatum "DATUM_B", "B", 3, 20, 5, 35, part.OriginElements.PlaneYZ
AddDatum "DATUM_C", "C", 4, 35, 5, 35, part.OriginElements.PlaneZX
AddFlatness
AddRoughness
AddFlagNote
AddNoa
AddTpsView "VIEW_FRONT", part.OriginElements.PlaneYZ, 0
AddTpsView "VIEW_TOP", part.OriginElements.PlaneXY, 1
AddCapture "CAPTURE_MACHINING"

WScript.Echo "[BLOCKED] DIM_LINEAR_FACE_FACE: CreateSemanticDimension failed in R21 probe; two-face probe raises unsupported geometry modal"
WScript.Echo "[BLOCKED] DIM_DIAMETER_CYLINDER: CreateSemanticDimension Diameter failed 0x80004005 in R21 probe"
WScript.Echo "[BLOCKED] DIM_LIMIT_DEVIATION: depends on native dimension creation, blocked by CreateSemanticDimension failure"
WScript.Echo "[BLOCKED] GDT_POSITION_DRF_ABC: CreateToleranceWithDRF probe did not expose FTA_Position; not mislabeling FTA_Symmetry"

If changed Then doc.Save
doc.Close
catia.Quit
WScript.Echo "[DONE] supported native FTA objects processed"
WScript.Quit 0

Sub AddDatum(ByVal objectName, ByVal label, ByVal faceIndex, ByVal x, ByVal y, ByVal z, ByVal fallbackPlane)
  If HasFtaName(objectName) Then WScript.Echo "[SKIP] " & objectName & " already exists": Exit Sub
  Dim us, ann, ds, e, d
  Set us = UserSurfaceForPadFace(faceIndex)
  If us Is Nothing Then Set us = UserSurfaceForObject(fallbackPlane)
  If us Is Nothing Then WScript.Echo "[BLOCKED] " & objectName & " face index unavailable=" & faceIndex: Exit Sub
  Err.Clear
  On Error Resume Next
  Set ann = annFactory.CreateEvoluateDatum(us, x, y, z, True)
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
  If e <> 0 Then WScript.Echo "[COM-ERROR] " & objectName & " set name/label 0x" & Hex(e) & " " & d: Exit Sub
  changed = True
  WScript.Echo "[ADDED] " & objectName & " nativeType=" & AnnType(ann)
End Sub

Sub AddFlatness()
  If HasFtaName("GDT_FLATNESS") Then WScript.Echo "[SKIP] GDT_FLATNESS already exists": Exit Sub
  Dim us, ann, tz, e, d
  Set us = UserSurfaceForPadFace(2)
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
  If e <> 0 Then WScript.Echo "[COM-ERROR] GDT_FLATNESS set value/name 0x" & Hex(e) & " " & d: Exit Sub
  changed = True
  WScript.Echo "[ADDED] GDT_FLATNESS nativeType=" & AnnType(ann)
End Sub

Sub AddRoughness()
  If HasFtaName("ROUGHNESS_RA32") Then WScript.Echo "[SKIP] ROUGHNESS_RA32 already exists": Exit Sub
  Dim us, ann, rough, e, d
  Set us = UserSurfaceForPadFace(3)
  If us Is Nothing Then Set us = UserSurfaceForPadFace(2)
  If us Is Nothing Then WScript.Echo "[BLOCKED] ROUGHNESS_RA32 no valid user surface": Exit Sub
  Err.Clear
  On Error Resume Next
  Set ann = annFactory.CreateRoughness(us)
  e = Err.Number: d = Err.Description
  On Error GoTo 0
  If e <> 0 Then WScript.Echo "[COM-ERROR] ROUGHNESS_RA32 CreateRoughness 0x" & Hex(e) & " " & d: Exit Sub
  If ObjectIsNothing(ann) Then WScript.Echo "[COM-ERROR] ROUGHNESS_RA32 CreateRoughness returned Nothing": Exit Sub
  Err.Clear
  On Error Resume Next
  ann.Name = "ROUGHNESS_RA32"
  Set rough = ann.Roughness
  rough.SetField 1, "Ra 3.2"
  ann.ModifyVisu
  e = Err.Number: d = Err.Description
  On Error GoTo 0
  If e <> 0 Then WScript.Echo "[COM-ERROR] ROUGHNESS_RA32 set field/name 0x" & Hex(e) & " " & d: Exit Sub
  changed = True
  WScript.Echo "[ADDED] ROUGHNESS_RA32 nativeType=" & AnnType(ann)
End Sub

Sub AddFlagNote()
  If HasFtaName("FLAG_NOTE_1") Then WScript.Echo "[SKIP] FLAG_NOTE_1 already exists": Exit Sub
  Dim us, ann, e, d
  Set us = UserSurfaceForPadFace(2)
  If us Is Nothing Then WScript.Echo "[BLOCKED] FLAG_NOTE_1 no valid user surface": Exit Sub
  Err.Clear
  On Error Resume Next
  Set ann = annFactory.CreateFlagNote(us)
  e = Err.Number: d = Err.Description
  On Error GoTo 0
  If e <> 0 Or ann Is Nothing Then WScript.Echo "[COM-ERROR] FLAG_NOTE_1 CreateFlagNote 0x" & Hex(e) & " " & d: Exit Sub
  Err.Clear
  On Error Resume Next
  ann.Name = "FLAG_NOTE_1"
  ann.ModifyVisu
  e = Err.Number: d = Err.Description
  On Error GoTo 0
  If e <> 0 Then WScript.Echo "[COM-ERROR] FLAG_NOTE_1 set name 0x" & Hex(e) & " " & d: Exit Sub
  changed = True
  WScript.Echo "[ADDED] FLAG_NOTE_1 nativeType=" & AnnType(ann)
End Sub

Sub AddNoa()
  If HasFtaName("NOA_GENERAL_NOTE") Then WScript.Echo "[SKIP] NOA_GENERAL_NOTE already exists": Exit Sub
  Dim us, noaObj, ann, e, d
  Set us = UserSurfaceForPadFace(2)
  If us Is Nothing Then WScript.Echo "[BLOCKED] NOA_GENERAL_NOTE no valid user surface": Exit Sub
  Err.Clear
  On Error Resume Next
  Set noaObj = annFactory.CreateTextNOA(us)
  noaObj.Text = "GENERAL NOTE"
  Set ann = annFactory.InstanciateNOA(noaObj, us)
  e = Err.Number: d = Err.Description
  On Error GoTo 0
  If e <> 0 Or ann Is Nothing Then WScript.Echo "[COM-ERROR] NOA_GENERAL_NOTE CreateTextNOA/InstanciateNOA 0x" & Hex(e) & " " & d: Exit Sub
  Err.Clear
  On Error Resume Next
  ann.Name = "NOA_GENERAL_NOTE"
  ann.ModifyVisu
  e = Err.Number: d = Err.Description
  On Error GoTo 0
  If e <> 0 Then WScript.Echo "[COM-ERROR] NOA_GENERAL_NOTE set name 0x" & Hex(e) & " " & d: Exit Sub
  changed = True
  WScript.Echo "[ADDED] NOA_GENERAL_NOTE nativeType=" & AnnType(ann)
End Sub

Sub AddTpsView(ByVal objectName, ByVal planeObj, ByVal viewType)
  If HasFtaName(objectName) Then WScript.Echo "[SKIP] " & objectName & " already exists": Exit Sub
  Dim factory, ref, view, e, d
  Set factory = annSet.TPSViewFactory
  Set ref = part.CreateReferenceFromObject(planeObj)
  Err.Clear
  On Error Resume Next
  Set view = factory.CreateView(ref, viewType)
  e = Err.Number: d = Err.Description
  On Error GoTo 0
  If e <> 0 Or view Is Nothing Then WScript.Echo "[COM-ERROR] " & objectName & " CreateView type=" & viewType & " 0x" & Hex(e) & " " & d: Exit Sub
  Err.Clear
  On Error Resume Next
  view.Name = objectName
  e = Err.Number: d = Err.Description
  On Error GoTo 0
  If e <> 0 Then WScript.Echo "[COM-WARN] " & objectName & " view.Name failed 0x" & Hex(e) & " " & d
  changed = True
  WScript.Echo "[ADDED] " & objectName & " nativeType=" & TypeName(view)
End Sub

Sub AddCapture(ByVal objectName)
  If HasFtaName(objectName) Then WScript.Echo "[SKIP] " & objectName & " already exists": Exit Sub
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
  If e <> 0 Then WScript.Echo "[COM-WARN] " & objectName & " capture detail assignment 0x" & Hex(e) & " " & d
  changed = True
  WScript.Echo "[ADDED] " & objectName & " nativeType=" & TypeName(cap)
End Sub

Function UserSurfaceForPadFace(ByVal faceIndex)
  Dim pad, ref
  Set UserSurfaceForPadFace = Nothing
  Set pad = part.Bodies.Item(1).Shapes.Item("Pad_FTA_Carrier")
  Err.Clear
  On Error Resume Next
  Set ref = part.CreateReferenceFromBRepName("Face:(Brp:(Pad_FTA_Carrier;" & faceIndex & ");None:();Cf11:());WithTemporaryBody;WithoutBuildError;WithSelectingFeatureSupport;MFBRepVersion_CXR15)", pad)
  Set UserSurfaceForPadFace = userSurfaces.Generate(ref)
  If Err.Number <> 0 Then Err.Clear: Set UserSurfaceForPadFace = Nothing
  On Error GoTo 0
End Function

Function UserSurfaceForObject(ByVal supportObj)
  Dim ref
  Set UserSurfaceForObject = Nothing
  Err.Clear
  On Error Resume Next
  Set ref = part.CreateReferenceFromObject(supportObj)
  Set UserSurfaceForObject = userSurfaces.Generate(ref)
  If Err.Number <> 0 Then Err.Clear: Set UserSurfaceForObject = Nothing
  On Error GoTo 0
End Function

Function ObjectIsNothing(ByVal obj)
  ObjectIsNothing = True
  Err.Clear
  On Error Resume Next
  If Not obj Is Nothing Then ObjectIsNothing = False
  If Err.Number <> 0 Then ObjectIsNothing = True: Err.Clear
  On Error GoTo 0
End Function

Function HasFtaName(ByVal objectName)
  Dim anns, views, caps, i
  HasFtaName = False
  Set anns = annSet.Annotations
  For i = 1 To anns.Count
    If LCase(SafeName(anns.Item(i))) = LCase(objectName) Then HasFtaName = True: Exit Function
  Next
  Err.Clear
  On Error Resume Next
  Set views = annSet.TPSViews
  For i = 1 To views.Count
    If LCase(SafeName(views.Item(i))) = LCase(objectName) Then HasFtaName = True: Exit Function
  Next
  Set caps = annSet.Captures
  For i = 1 To caps.Count
    If LCase(SafeName(caps.Item(i))) = LCase(objectName) Then HasFtaName = True: Exit Function
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

Function AnnType(ByVal ann)
  AnnType = TypeName(ann)
  Err.Clear
  On Error Resume Next
  AnnType = AnnType & "/Type=" & ann.Type & "/SuperType=" & ann.SuperType
  If Err.Number <> 0 Then Err.Clear
  On Error GoTo 0
End Function

Function OpenDocument(ByVal p)
  Dim i, existing
  Err.Clear
  On Error Resume Next
  For i = 1 To catia.Documents.Count
    Set existing = catia.Documents.Item(i)
    If LCase(CStr(existing.FullName)) = LCase(CStr(p)) Then
      Set OpenDocument = existing
      Err.Clear
      On Error GoTo 0
      WScript.Echo "[REUSE-OPEN] " & p
      Exit Function
    End If
    Err.Clear
  Next
  On Error GoTo 0
  Err.Clear
  On Error Resume Next
  Set OpenDocument = catia.Documents.Open(p)
  Dim e, d: e = Err.Number: d = Err.Description
  On Error GoTo 0
  If e <> 0 Or OpenDocument Is Nothing Then Fatal "Open failed 0x" & Hex(e) & " " & d, 8
End Function

Function CreateCatia()
  Err.Clear
  On Error Resume Next
  Set CreateCatia = CreateObject("CATIA.Application")
  Dim e, d: e = Err.Number: d = Err.Description
  On Error GoTo 0
  If e <> 0 Or CreateCatia Is Nothing Then
    WScript.Echo "[ERROR] Create CATIA.Application 0x" & Hex(e) & " " & d
    WScript.Quit 9
  End If
End Function

Function RuntimeText(): RuntimeText = "V" & cfg.Version & "R" & cfg.Release & "SP" & cfg.ServicePack: End Function
Sub Fatal(ByVal message, ByVal code)
  WScript.Echo "[ERROR] " & message
  On Error Resume Next
  If Not doc Is Nothing Then doc.Close
  If Not catia Is Nothing Then catia.Quit
  WScript.Quit code
End Sub
