Option Explicit

' Non-saving FTA Automation probe for CATIA V5R21. Opens a scaffold, attempts native
' AnnotationSet/UserSurface/text creation in memory, and closes without SaveAs/Save.

Dim fso, fixtureDir, scaffoldPath, catia, cfg, doc, part
Set fso = CreateObject("Scripting.FileSystemObject")
If WScript.Arguments.Count = 1 And LCase(WScript.Arguments(0)) = "--syntax-check" Then
  WScript.Echo "[SYNTAX-OK] probe_fta_workbench.vbs"
  WScript.Quit 0
End If
If WScript.Arguments.Count <> 1 Then
  WScript.Echo "Usage: cscript //nologo probe_fta_workbench.vbs <fixture-directory>"
  WScript.Quit 2
End If

fixtureDir = fso.GetAbsolutePathName(WScript.Arguments(0))
scaffoldPath = fso.BuildPath(fixtureDir, "fta_all_semantic_types_scaffold.CATPart")
If Not fso.FileExists(scaffoldPath) Then
  WScript.Echo "[ERROR] Missing scaffold " & scaffoldPath
  WScript.Quit 3
End If

Set catia = CreateCatia()
catia.Visible = True
catia.DisplayFileAlerts = False
Set cfg = catia.SystemConfiguration
If cfg.Version <> 5 Or cfg.Release <> 21 Then Fatal "Expected CATIA V5R21, got " & RuntimeText(), 4
WScript.Echo "[CATIA] " & RuntimeText()

Set doc = OpenDocument(scaffoldPath)
Set part = doc.Part
WScript.Echo "[OPEN] " & scaffoldPath

ProbeWorkbenchCommand "Functional Tolerancing & Annotation"
ProbeWorkbenchCommand "FTA"
ProbeWorkbenchCommand "Product Functional Tolerancing & Annotation"
ProbeAnnotationCreation
ProbeFactoryEnums

On Error Resume Next
doc.Close
catia.Quit
WScript.Echo "[DONE] FTA probe closed without saving"
WScript.Quit 0

Sub ProbeWorkbenchCommand(ByVal workbenchName)
  Err.Clear
  On Error Resume Next
  catia.StartWorkbench workbenchName
  Dim e, d: e = Err.Number: d = Err.Description
  On Error GoTo 0
  If e = 0 Then
    WScript.Echo "[WORKBENCH-OK] StartWorkbench " & workbenchName
  Else
    WScript.Echo "[WORKBENCH-ERROR] StartWorkbench " & workbenchName & " 0x" & Hex(e) & " " & d
  End If
End Sub

Sub ProbeFactoryEnums()
  Dim annSets, annSet, faceRef, userSurfaces, userSurface, annFactory, ann, drf, i, j, made
  Err.Clear
  On Error Resume Next
  Set annSets = part.AnnotationSets
  Set annSet = annSets.Add("ISO_3D")
  Set faceRef = part.CreateReferenceFromBRepName("Face:(Brp:(Pad_FTA_Carrier;2);None:();Cf11:());WithTemporaryBody;WithoutBuildError;WithSelectingFeatureSupport;MFBRepVersion_CXR15)", part.Bodies.Item(1).Shapes.Item("Pad_FTA_Carrier"))
  Set userSurfaces = part.UserSurfaces
  Set userSurface = userSurfaces.Generate(faceRef)
  Set annFactory = annSet.AnnotationFactory
  Dim e, d: e = Err.Number: d = Err.Description
  On Error GoTo 0
  If e <> 0 Or annFactory Is Nothing Then
    WScript.Echo "[ENUM-SKIP] factory setup failed 0x" & Hex(e) & " " & d
    Exit Sub
  End If

  made = 0
  For i = 0 To 12
    For j = 0 To 8
      Set ann = Nothing
      Err.Clear
      On Error Resume Next
      Set ann = annFactory.CreateSemanticDimension(userSurface, i, j)
      e = Err.Number: d = Err.Description
      On Error GoTo 0
      If e = 0 And Not ann Is Nothing Then
        WScript.Echo "[ENUM-OK] CreateSemanticDimension type=" & i & " subtype=" & j & " annType=" & AnnotationTypeText(ann)
        made = made + 1
        If made >= 8 Then Exit For
      End If
    Next
    If made >= 8 Then Exit For
  Next
  If made = 0 Then WScript.Echo "[ENUM-BLOCKED] CreateSemanticDimension no successful type/subtype in probe range"

  made = 0
  For i = 0 To 20
    For j = 0 To 12
      Set ann = Nothing
      Err.Clear
      On Error Resume Next
      Set ann = annFactory.CreateNonSemanticDimension(userSurface, i, j)
      e = Err.Number: d = Err.Description
      On Error GoTo 0
      If e = 0 And Not ann Is Nothing Then
        WScript.Echo "[ENUM-OK] CreateNonSemanticDimension type=" & i & " subtype=" & j & " annType=" & AnnotationTypeText(ann)
        made = made + 1
        If made >= 8 Then Exit For
      End If
    Next
    If made >= 8 Then Exit For
  Next
  If made = 0 Then WScript.Echo "[ENUM-BLOCKED] CreateNonSemanticDimension no successful type/subtype in numeric probe range"

  ProbeDimensionString annFactory, userSurface, "Length", "Distance"
  ProbeDimensionString annFactory, userSurface, "Length", "Offset"
  ProbeDimensionString annFactory, userSurface, "Distance", "Distance"
  ProbeDimensionString annFactory, userSurface, "Diameter", "Diameter"
  ProbeDimensionString annFactory, userSurface, "Radius", "Radius"
  WScript.Echo "[ENUM-BLOCKED] two-face dimension probe skipped after R21 GUI modal error: selected geometry unsupported or not associated with annotation geometry set"

  For i = 0 To 25
    Set ann = Nothing
    Err.Clear
    On Error Resume Next
    Set ann = annFactory.CreateToleranceWithoutDRF(i, userSurface)
    e = Err.Number: d = Err.Description
    On Error GoTo 0
    If e = 0 And Not ann Is Nothing Then
      WScript.Echo "[ENUM-OK] CreateToleranceWithoutDRF index=" & i & " annType=" & AnnotationTypeText(ann)
    End If
  Next

  Err.Clear
  On Error Resume Next
  Set drf = annFactory.CreateDatumReferenceFrame()
  e = Err.Number: d = Err.Description
  On Error GoTo 0
  If e = 0 And Not drf Is Nothing Then
    WScript.Echo "[ENUM-OK] CreateDatumReferenceFrame annType=" & AnnotationTypeText(drf)
    For i = 0 To 25
      Set ann = Nothing
      Err.Clear
      On Error Resume Next
      Set ann = annFactory.CreateToleranceWithDRF(i, userSurface, drf)
      e = Err.Number: d = Err.Description
      On Error GoTo 0
      If e = 0 And Not ann Is Nothing Then
        WScript.Echo "[ENUM-OK] CreateToleranceWithDRF index=" & i & " annType=" & AnnotationTypeText(ann)
      End If
    Next
  Else
    WScript.Echo "[ENUM-BLOCKED] CreateDatumReferenceFrame 0x" & Hex(e) & " " & d
  End If
End Sub


Sub ProbeDimensionString(ByVal annFactory, ByVal userSurface, ByVal dimType, ByVal subType)
  Dim ann, e, d
  Set ann = Nothing
  Err.Clear
  On Error Resume Next
  Set ann = annFactory.CreateSemanticDimension(userSurface, dimType, subType)
  e = Err.Number: d = Err.Description
  On Error GoTo 0
  If e = 0 And Not ann Is Nothing Then
    WScript.Echo "[ENUM-OK] CreateSemanticDimension type=" & dimType & " subtype=" & subType & " annType=" & AnnotationTypeText(ann)
  Else
    WScript.Echo "[ENUM-ERR] CreateSemanticDimension type=" & dimType & " subtype=" & subType & " 0x" & Hex(e) & " " & d
  End If
End Sub

Function AnnotationTypeText(ByVal ann)
  AnnotationTypeText = TypeName(ann)
  Err.Clear
  On Error Resume Next
  AnnotationTypeText = AnnotationTypeText & "/Type=" & ann.Type & "/SuperType=" & ann.SuperType
  If Err.Number <> 0 Then Err.Clear
  On Error GoTo 0
End Function

Sub ProbeAnnotationCreation()
  Dim annSets, annSet, faceRef, userSurfaces, userSurface, annFactory, ann
  Err.Clear
  On Error Resume Next
  Set annSets = part.AnnotationSets
  Dim e, d: e = Err.Number: d = Err.Description
  On Error GoTo 0
  If e <> 0 Or annSets Is Nothing Then
    WScript.Echo "[FTA-ERROR] part.AnnotationSets 0x" & Hex(e) & " " & d
    Exit Sub
  End If
  WScript.Echo "[FTA] initial AnnotationSets.Count=" & annSets.Count

  Err.Clear
  On Error Resume Next
  Set annSet = annSets.Add("ISO_3D")
  e = Err.Number: d = Err.Description
  On Error GoTo 0
  If e <> 0 Or annSet Is Nothing Then
    WScript.Echo "[FTA-ERROR] AnnotationSets.Add ISO_3D 0x" & Hex(e) & " " & d
    Exit Sub
  End If
  WScript.Echo "[FTA-OK] AnnotationSets.Add returned " & TypeName(annSet) & " count=" & annSets.Count
  Err.Clear
  On Error Resume Next
  annSet.Name = "PROBE_Annotation_Set_NotSaved"
  e = Err.Number: d = Err.Description
  On Error GoTo 0
  If e <> 0 Then
    WScript.Echo "[FTA-WARN] AnnotationSet.Name is not settable here 0x" & Hex(e) & " " & d
  Else
    WScript.Echo "[FTA-OK] AnnotationSet.Name assigned"
  End If

  Err.Clear
  On Error Resume Next
  Set faceRef = part.CreateReferenceFromBRepName("Face:(Brp:(Pad_FTA_Carrier;2);None:();Cf11:());WithTemporaryBody;WithoutBuildError;WithSelectingFeatureSupport;MFBRepVersion_CXR15)", part.Bodies.Item(1).Shapes.Item("Pad_FTA_Carrier"))
  Set userSurfaces = part.UserSurfaces
  Set userSurface = userSurfaces.Generate(faceRef)
  e = Err.Number: d = Err.Description
  On Error GoTo 0
  If e <> 0 Or userSurface Is Nothing Then
    WScript.Echo "[FTA-ERROR] UserSurfaces.Generate top face 0x" & Hex(e) & " " & d
    Exit Sub
  End If
  WScript.Echo "[FTA-OK] UserSurface returned " & TypeName(userSurface)

  Err.Clear
  On Error Resume Next
  Set annFactory = annSet.AnnotationFactory
  Set ann = annFactory.CreateEvoluateText(userSurface, 20, 20, 35, True)
  e = Err.Number: d = Err.Description
  On Error GoTo 0
  If e <> 0 Or ann Is Nothing Then
    WScript.Echo "[FTA-ERROR] AnnotationFactory.CreateEvoluateText 0x" & Hex(e) & " " & d
    Exit Sub
  End If
  ann.Name = "PROBE_TEXT_NOT_SAVED"
  WScript.Echo "[FTA-OK] CreateEvoluateText returned " & TypeName(ann)
End Sub

Function OpenDocument(ByVal path)
  Err.Clear
  On Error Resume Next
  Set OpenDocument = catia.Documents.Open(path)
  Dim e, d: e = Err.Number: d = Err.Description
  On Error GoTo 0
  If e <> 0 Or OpenDocument Is Nothing Then Fatal "Open scaffold failed 0x" & Hex(e) & " " & d, 5
End Function

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

Function RuntimeText(): RuntimeText = "V" & cfg.Version & "R" & cfg.Release & "SP" & cfg.ServicePack: End Function
Sub Fatal(ByVal message, ByVal code)
  WScript.Echo "[ERROR] " & message
  On Error Resume Next
  If Not doc Is Nothing Then doc.Close
  If Not catia Is Nothing Then catia.Quit
  WScript.Quit code
End Sub
