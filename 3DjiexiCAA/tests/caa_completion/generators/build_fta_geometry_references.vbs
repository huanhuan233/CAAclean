Option Explicit

' Builds fta_geometry_references.CATPart from its scaffold and adds native FTA annotations
' to real geometry references where CATIA V5R21 Automation accepts the support.

Dim fso, fixtureDir, scaffoldPath, formalPath, catia, cfg, doc, part, annSet, annFactory, userSurfaces
Dim changed, messages
Set fso = CreateObject("Scripting.FileSystemObject")
If WScript.Arguments.Count = 1 And LCase(WScript.Arguments(0)) = "--syntax-check" Then
  WScript.Echo "[SYNTAX-OK] build_fta_geometry_references.vbs"
  WScript.Quit 0
End If
If WScript.Arguments.Count <> 1 Then
  WScript.Echo "Usage: cscript //nologo build_fta_geometry_references.vbs <fixture-directory>"
  WScript.Quit 2
End If

fixtureDir = fso.GetAbsolutePathName(WScript.Arguments(0))
scaffoldPath = fso.BuildPath(fixtureDir, "fta_geometry_references_scaffold.CATPart")
formalPath = fso.BuildPath(fixtureDir, "fta_geometry_references.CATPart")
If Not fso.FileExists(scaffoldPath) Then WScript.Echo "[ERROR] Missing scaffold " & scaffoldPath: WScript.Quit 3

Set catia = CreateCatia()
catia.Visible = True
catia.DisplayFileAlerts = False
Set cfg = catia.SystemConfiguration
If cfg.Version <> 5 Or cfg.Release <> 21 Then Fatal "Expected CATIA V5R21, got " & RuntimeText(), 4

If fso.FileExists(formalPath) Then
  Set doc = catia.Documents.Open(formalPath)
  WScript.Echo "[OPEN] existing formal " & formalPath
Else
  Set doc = catia.Documents.Open(scaffoldPath)
  doc.SaveAs formalPath
  WScript.Echo "[SAVED-AS] " & formalPath
End If

Set part = doc.Part
EnsureReferenceGeometry
Set annSet = EnsureAnnotationSet()
Set annFactory = annSet.AnnotationFactory
Set userSurfaces = part.UserSurfaces
changed = False: messages = ""

AddTextOnSupport "REF_FACE", "face reference", PadFaceRef(2)
AddTextOnSupport "REF_DATUM_PLANE", "datum plane reference", part.CreateReferenceFromObject(part.OriginElements.PlaneXY)
WScript.Echo "[BLOCKED] REF_AXIS V5R21 FTA UserSurfaces.Generate rejected the hybrid axis line: not a final 3D result support"
WScript.Echo "[BLOCKED] REF_VERTEX V5R21 FTA UserSurfaces.Generate rejected the hybrid point: not a final 3D result support"
WScript.Echo "[BLOCKED] REF_EDGE V5R21 FTA UserSurfaces.Generate rejected the hybrid line: not a final 3D result support"
WScript.Echo "[BLOCKED] REF_TTRS_MULTI V5R21 FTA CreateEvoluateText on MakeUserSurfaceNode raised unsupported-geometry modal"

If changed Then doc.Save
doc.Close
catia.Quit
WScript.Echo "[DONE] fta_geometry_references processed"
WScript.Quit 0

Sub EnsureReferenceGeometry()
  Dim hb, hsf, p1, p2, p3, line1, axisLine
  Err.Clear
  On Error Resume Next
  Set hb = part.HybridBodies.Item("FTA_ReferenceGeometry")
  If Err.Number <> 0 Or hb Is Nothing Then
    Err.Clear
    Set hb = part.HybridBodies.Add()
    hb.Name = "FTA_ReferenceGeometry"
  End If
  Set hsf = part.HybridShapeFactory
  If Not HybridShapeExists(hb, "REF_VERTEX_POINT") Then
    Set p1 = hsf.AddNewPointCoord(0, 0, 35)
    p1.Name = "REF_VERTEX_POINT"
    hb.AppendHybridShape p1
  End If
  If Not HybridShapeExists(hb, "REF_EDGE_LINE") Then
    Set p1 = hsf.AddNewPointCoord(-60, -40, 25)
    p1.Name = "REF_EDGE_LINE_P1": hb.AppendHybridShape p1
    Set p2 = hsf.AddNewPointCoord(60, -40, 25)
    p2.Name = "REF_EDGE_LINE_P2": hb.AppendHybridShape p2
    Set line1 = hsf.AddNewLinePtPt(p1, p2)
    line1.Name = "REF_EDGE_LINE"
    hb.AppendHybridShape line1
  End If
  If Not HybridShapeExists(hb, "REF_AXIS_LINE") Then
    Set p1 = hsf.AddNewPointCoord(0, 0, -10)
    p1.Name = "REF_AXIS_P1": hb.AppendHybridShape p1
    Set p2 = hsf.AddNewPointCoord(0, 0, 40)
    p2.Name = "REF_AXIS_P2": hb.AppendHybridShape p2
    Set axisLine = hsf.AddNewLinePtPt(p1, p2)
    axisLine.Name = "REF_AXIS_LINE"
    hb.AppendHybridShape axisLine
  End If
  part.Update
  On Error GoTo 0
End Sub

Function EnsureAnnotationSet()
  Dim sets
  Set sets = part.AnnotationSets
  If sets.Count = 0 Then
    Set EnsureAnnotationSet = sets.Add("ISO_3D")
  Else
    Set EnsureAnnotationSet = sets.Item(1)
  End If
End Function

Sub AddTextOnSupport(ByVal objectName, ByVal textValue, ByVal supportRef)
  If HasAnnotation(objectName) Then WScript.Echo "[SKIP] " & objectName: Exit Sub
  If ObjectIsNothing(supportRef) Then WScript.Echo "[BLOCKED] " & objectName & " support reference is Nothing": Exit Sub
  Dim us, ann, txt, e, d
  Err.Clear
  On Error Resume Next
  Set us = userSurfaces.Generate(supportRef)
  Set ann = annFactory.CreateEvoluateText(us, 10, 10, 40, True)
  e = Err.Number: d = Err.Description
  On Error GoTo 0
  If e <> 0 Or ObjectIsNothing(ann) Then WScript.Echo "[COM-ERROR] " & objectName & " CreateEvoluateText 0x" & Hex(e) & " " & d: Exit Sub
  Err.Clear
  On Error Resume Next
  ann.Name = objectName
  Set txt = ann.Text
  txt.Text = textValue
  ann.ModifyVisu
  e = Err.Number: d = Err.Description
  On Error GoTo 0
  If e <> 0 Then WScript.Echo "[COM-ERROR] " & objectName & " set name/text 0x" & Hex(e) & " " & d: Exit Sub
  changed = True
  doc.Save
  WScript.Echo "[ADDED] " & objectName & " native annotation on " & textValue
End Sub

Sub AddMultiGeometry()
  If HasAnnotation("REF_TTRS_MULTI") Then WScript.Echo "[SKIP] REF_TTRS_MULTI": Exit Sub
  Dim ref1, ref2, us1, us2, node, ann, txt, e, d
  Set ref1 = PadFaceRef(2)
  Set ref2 = PadFaceRef(5)
  If ObjectIsNothing(ref1) Or ObjectIsNothing(ref2) Then WScript.Echo "[BLOCKED] REF_TTRS_MULTI face references unavailable": Exit Sub
  Err.Clear
  On Error Resume Next
  Set us1 = userSurfaces.Generate(ref1)
  Set us2 = userSurfaces.Generate(ref2)
  Set node = userSurfaces.MakeUserSurfaceNode(us1, us2)
  Set ann = annFactory.CreateEvoluateText(node, 20, 20, 45, True)
  e = Err.Number: d = Err.Description
  On Error GoTo 0
  If e <> 0 Or ObjectIsNothing(ann) Then WScript.Echo "[COM-ERROR] REF_TTRS_MULTI multi user surface 0x" & Hex(e) & " " & d: Exit Sub
  Err.Clear
  On Error Resume Next
  ann.Name = "REF_TTRS_MULTI"
  Set txt = ann.Text
  txt.Text = "multi geometry reference"
  ann.ModifyVisu
  e = Err.Number: d = Err.Description
  On Error GoTo 0
  If e <> 0 Then WScript.Echo "[COM-ERROR] REF_TTRS_MULTI set name/text 0x" & Hex(e) & " " & d: Exit Sub
  changed = True
  doc.Save
  WScript.Echo "[ADDED] REF_TTRS_MULTI native annotation on UserSurface node"
End Sub

Function PadFaceRef(ByVal faceIndex)
  Dim pad
  Set PadFaceRef = Nothing
  Err.Clear
  On Error Resume Next
  Set pad = part.Bodies.Item(1).Shapes.Item("Pad_FTA_Carrier")
  Set PadFaceRef = part.CreateReferenceFromBRepName("Face:(Brp:(Pad_FTA_Carrier;" & faceIndex & ");None:();Cf11:());WithTemporaryBody;WithoutBuildError;WithSelectingFeatureSupport;MFBRepVersion_CXR15)", pad)
  If Err.Number <> 0 Then Err.Clear: Set PadFaceRef = Nothing
  On Error GoTo 0
End Function

Function ObjectRefByName(ByVal outerCollName, ByVal outerName, ByVal innerCollName, ByVal innerName)
  Dim outer, innerObj
  Set ObjectRefByName = Nothing
  Err.Clear
  On Error Resume Next
  Set outer = part.HybridBodies.Item(outerName)
  Set innerObj = outer.HybridShapes.Item(innerName)
  Set ObjectRefByName = part.CreateReferenceFromObject(innerObj)
  If Err.Number <> 0 Then Err.Clear: Set ObjectRefByName = Nothing
  On Error GoTo 0
End Function

Function HybridShapeExists(ByVal hb, ByVal name)
  Dim obj
  HybridShapeExists = False
  Err.Clear
  On Error Resume Next
  Set obj = hb.HybridShapes.Item(name)
  If Err.Number = 0 And Not obj Is Nothing Then HybridShapeExists = True
  Err.Clear
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

Function HasAnnotation(ByVal objectName)
  Dim anns, i
  HasAnnotation = False
  Err.Clear
  On Error Resume Next
  Set anns = annSet.Annotations
  For i = 1 To anns.Count
    If LCase(CStr(anns.Item(i).Name)) = LCase(objectName) Then HasAnnotation = True: Exit Function
  Next
  Err.Clear
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
