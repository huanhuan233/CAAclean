Option Explicit

' CATIA V5R21 standalone advanced-fixture repair generator v1.0.3.
'
' Usage:
'   cscript //nologo generate_one_advanced_fixture.vbs <fixture-dir> <case> [guided]
'
' Cases:
'   fillet | chamfer | shaft_groove | rib_slot | shell_thickness |
'   pattern | boolean | gsd_analytic | pressure
'
' Safety:
'   1. Builds and reopens a temporary CATPart first.
'   2. Replaces the requested fixture only after verification succeeds.
'   3. Copies an existing fixture into repair_backups before replacement.
'   4. Never touches the core fixtures.
'   5. Supports --syntax-check without starting CATIA.

Const CAT_TANGENCY_FILLET = 1
Const CAT_MINIMAL_FILLET = 0
' CATIA enums are zero based.  These values are deliberately explicit because
' Windows Script Host does not import CATIA type-library enum symbols.
Const CAT_TANGENCY_CHAMFER = 0
Const CAT_LENGTH_ANGLE_CHAMFER = 1
Const CAT_NO_REVERSE_CHAMFER = 0

Dim fso, outputDir, caseName, guidedMode
Dim catia, cfg, ownsCatia, doc, ledger, repairLedger
Dim fileName, finalPath, tempPath, expectedNames, runtimeName

Set fso = CreateObject("Scripting.FileSystemObject")
Set catia = Nothing
Set cfg = Nothing
Set doc = Nothing
Set ledger = Nothing
Set repairLedger = Nothing
ownsCatia = False

If WScript.Arguments.Count = 1 Then
  If LCase(Trim(WScript.Arguments(0))) = "--syntax-check" Then
    WScript.Echo "[SYNTAX-OK] generate_one_advanced_fixture.vbs"
    WScript.Quit 0
  End If
End If

If WScript.Arguments.Count < 2 Or WScript.Arguments.Count > 3 Then
  WScript.Echo "Usage: cscript //nologo generate_one_advanced_fixture.vbs <fixture-dir> <case> [guided]"
  WScript.Quit 2
End If

outputDir = fso.GetAbsolutePathName(WScript.Arguments(0))
caseName = LCase(Trim(WScript.Arguments(1)))
guidedMode = False
If WScript.Arguments.Count = 3 Then guidedMode = (LCase(Trim(WScript.Arguments(2))) = "guided")

EnsureFolder outputDir
ResolveCase caseName, fileName, expectedNames
finalPath = fso.BuildPath(outputDir, fileName)
tempPath = fso.BuildPath(outputDir, "__repair_tmp_" & fileName)
DeleteIfExists tempPath

Set ledger = fso.OpenTextFile(fso.BuildPath(outputDir, "generation_ledger.tsv"), 8, True, 0)
Set repairLedger = fso.OpenTextFile(fso.BuildPath(outputDir, "advanced_repair_ledger.tsv"), 8, True, 0)

On Error Resume Next
Err.Clear
Set catia = GetObject(, "CATIA.Application")
If Err.Number <> 0 Or catia Is Nothing Then
  Err.Clear
  Set catia = CreateObject("CATIA.Application")
  RequireSuccess "CreateObject(CATIA.Application)"
  ownsCatia = True
End If

catia.Visible = True
Err.Clear
Set cfg = catia.SystemConfiguration
RequireSuccess "Read CATIA SystemConfiguration"
If cfg.Version <> 5 Or cfg.Release <> 21 Then
  FailCase "Expected CATIA V5R21 but found V" & cfg.Version & "R" & cfg.Release, 9003, 3
End If
runtimeName = "V" & cfg.Version & "R" & cfg.Release & "SP" & cfg.ServicePack

WScript.Echo "[BUILD] " & fileName & "  mode=" & ModeText()
Err.Clear
Set doc = catia.Documents.Add("Part")
RequireSuccess "Documents.Add(Part)"
doc.Activate
RequireSuccess "Activate new Part"

Select Case caseName
  Case "fillet": BuildFillet doc
  Case "chamfer": BuildChamfer doc
  Case "shaft_groove": BuildShaftGroove doc
  Case "rib_slot": BuildRibSlot doc
  Case "shell_thickness": BuildShellThickness doc
  Case "pattern": BuildPattern doc
  Case "boolean": BuildBoolean doc
  Case "gsd_analytic": BuildGsdAnalytic doc
  Case "pressure": BuildPressure doc
End Select

Err.Clear
doc.Part.Update
RequireSuccess "Final Part.Update"
VerifyNames doc, expectedNames, "in-memory final update"
If caseName <> "gsd_analytic" Then AssertPositiveVolume doc, "in-memory fixture"

Err.Clear
doc.SaveAs tempPath
RequireSuccess "SaveAs temporary CATPart"
Err.Clear
doc.Close
RequireSuccess "Close temporary CATPart"
Set doc = Nothing

WScript.Echo "[VERIFY] close/reopen and native history"
Err.Clear
Set doc = catia.Documents.Open(tempPath)
RequireSuccess "Reopen temporary CATPart"
Err.Clear
doc.Part.Update
RequireSuccess "Update reopened CATPart"
VerifyNames doc, expectedNames, "after close/reopen"
If caseName <> "gsd_analytic" Then AssertPositiveVolume doc, "reopened fixture"
Err.Clear
doc.Close
RequireSuccess "Close verified CATPart"
Set doc = Nothing

BackupExisting finalPath
Err.Clear
fso.CopyFile tempPath, finalPath, True
RequireSuccess "Publish verified CATPart"
DeleteIfExists tempPath

WriteResult "generated", "standalone repair; close/reopen verified; expected history: " & Join(expectedNames, ",")
WScript.Echo "[GENERATED] " & finalPath
WScript.Echo "[DONE] Existing file was replaced only after verification; backup is under repair_backups when applicable."
Cleanup 0
WScript.Quit 0

Sub ResolveCase(ByVal requested, ByRef resolvedFile, ByRef names)
  Select Case requested
    Case "fillet"
      resolvedFile = "pd_fillet_constant.CATPart"
      names = Array("Pad_Fillet_Base", "Fillet_Constant_R5")
    Case "chamfer"
      resolvedFile = "pd_chamfer_variants.CATPart"
      names = Array("Pad_Chamfer_Base", "Chamfer_LengthAngle")
    Case "shaft_groove"
      resolvedFile = "pd_shaft_groove.CATPart"
      names = Array("Shaft_Full360", "Groove_Annular360")
    Case "rib_slot"
      resolvedFile = "pd_rib_slot.CATPart"
      names = Array("Rib_Straight", "Slot_Straight")
    Case "shell_thickness"
      resolvedFile = "pd_shell_thickness.CATPart"
      names = Array("Pad_Shell_Base", "Shell_3mm", "Thickness_Local1mm")
    Case "pattern"
      resolvedFile = "pd_patterns.CATPart"
      names = Array("Pad_Pattern_Base", "Pad_Pattern_Seed", "RectangularPattern_3x2")
    Case "boolean"
      resolvedFile = "pd_multibody_booleans.CATPart"
      names = Array("Boolean_Add", "Boolean_Remove", "Boolean_Assemble", "Boolean_Intersect")
    Case "gsd_analytic"
      resolvedFile = "gsd_analytic_elements.CATPart"
      names = Array("Point_Origin", "Point_End", "Line_PointPoint", "Plane_Offset25", "AxisSystem_Test")
    Case "pressure"
      resolvedFile = "pressure_pad_pocket_fillet_chamfer.CATPart"
      names = Array("Pad_Pressure", "Pocket_Pressure", "Fillet_Pressure", "Chamfer_Pressure")
    Case Else
      WScript.Echo "[ERROR] Unknown case: " & requested
      WScript.Echo "Allowed: fillet chamfer shaft_groove rib_slot shell_thickness pattern boolean gsd_analytic pressure"
      WScript.Quit 2
  End Select
End Sub

Sub BuildFillet(ByVal partDoc)
  Dim part, body, planeRef, sketch, pad, edgeBoundary, fillet
  Dim beforeShapes, afterShapes, errNo, errHex, errText, errSource
  Set part = partDoc.Part
  Set body = MainBody(part)
  Set planeRef = part.CreateReferenceFromObject(part.OriginElements.PlaneXY)
  RequireSuccess "Reference PlaneXY"
  Set sketch = RectSketch(body, planeRef, "Sketch_Fillet_Base", -45, -30, 45, 30)
  Set pad = part.ShapeFactory.AddNewPad(sketch, 24)
  RequireSuccess "Create Pad_Fillet_Base"
  pad.Name = "Pad_Fillet_Base"
  part.UpdateObject pad
  RequireSuccess "Update Pad_Fillet_Base"
  Set edgeBoundary = PadVerticalEdgeReference(partDoc, part, pad, sketch, 1, 2, "fillet")
  WScript.Echo "[TOPOLOGY] stage=fillet edgeType=" & ObjectTypeText(edgeBoundary) & _
    " edgeCATIAType=" & ObjectCATIAType(edgeBoundary) & _
    " selectionCount=" & SelectionCountText(partDoc.Selection) & _
    " inWorkObject=" & InWorkObjectText(part)
  DumpFeatureInventory partDoc, "fillet before edge fillet call"
  AssertPositiveVolume partDoc, "fillet before edge fillet call"

  beforeShapes = BodyShapesCount(body)
  Set fillet = Nothing
  Err.Clear
  WScript.Echo "[FEATURE-CALL] case=fillet stage=create method=AddNewEdgeFilletWithConstantRadius" & _
    " beforeShapes=" & CStr(beforeShapes) & _
    " boundaryType=" & ObjectTypeText(edgeBoundary) & _
    " boundaryCATIAType=" & ObjectCATIAType(edgeBoundary) & _
    " inWorkObject=" & InWorkObjectText(part)
  ' Dassault's CAAPriCreateEdgeFillet.CATScript passes this BRep Reference here.
  On Error Resume Next
  Set fillet = part.ShapeFactory.AddNewEdgeFilletWithConstantRadius(edgeBoundary, CAT_MINIMAL_FILLET, 5)
  errNo = Err.Number
  errHex = Hex(Err.Number)
  errText = Err.Description
  errSource = Err.Source
  Err.Clear
  On Error GoTo 0
  afterShapes = BodyShapesCount(body)
  If errNo <> 0 Then
    WScript.Echo "[COM-ERROR] case=fillet stage=create method=AddNewEdgeFilletWithConstantRadius" & _
      " number=" & CStr(errNo) & " hex=0x" & errHex & _
      " description=" & Clean(errText) & " source=" & Clean(errSource) & _
      " returnedNothing=" & BoolText(fillet Is Nothing) & _
      " beforeShapes=" & CStr(beforeShapes) & " afterShapes=" & CStr(afterShapes)
    DumpFeatureInventory partDoc, "fillet COM failure after AddNewEdgeFilletWithConstantRadius"
    FailCase "AddNewEdgeFilletWithConstantRadius failed: " & errText, errNo, 10
  End If
  If fillet Is Nothing Then
    WScript.Echo "[COM-ERROR] case=fillet stage=create method=AddNewEdgeFilletWithConstantRadius" & _
      " number=0 hex=0x0 description=CATIA returned Nothing source=" & _
      " beforeShapes=" & CStr(beforeShapes) & " afterShapes=" & CStr(afterShapes)
    DumpFeatureInventory partDoc, "fillet returned Nothing after AddNewEdgeFilletWithConstantRadius"
    FailCase "AddNewEdgeFilletWithConstantRadius returned Nothing", 9023, 10
  End If
  WScript.Echo "[FEATURE] case=fillet stage=create returnedType=" & ObjectTypeText(fillet) & _
    " returnedCATIAType=" & ObjectCATIAType(fillet) & _
    " beforeShapes=" & CStr(beforeShapes) & " afterShapes=" & CStr(afterShapes)
  If afterShapes <= beforeShapes Then
    DumpFeatureInventory partDoc, "fillet shape count did not increase after factory call"
    FailCase "AddNewEdgeFilletWithConstantRadius returned an object but Body.Shapes.Count did not increase", 9024, 10
  End If
  partDoc.Selection.Clear
  RequireObject fillet, "constant-radius fillet factory result"
  RequireSuccess "Clear selection after constant-radius fillet"
  CommitNamedFeature part, fillet, "Fillet_Constant_R5", "constant-radius fillet"
  DumpFeatureInventory partDoc, "fillet after update"
  AssertPositiveVolume partDoc, "fillet after Fillet_Constant_R5"
End Sub

Sub BuildChamfer(ByVal partDoc)
  Dim part, body, planeRef, sketch, pad, edgeBoundary, chamfer
  Dim beforeShapes, afterShapes, errNo, errHex, errText, errSource
  Set part = partDoc.Part
  Set body = MainBody(part)
  Set planeRef = part.CreateReferenceFromObject(part.OriginElements.PlaneXY)
  RequireSuccess "Reference PlaneXY"
  Set sketch = RectSketch(body, planeRef, "Sketch_Chamfer_Base", -45, -30, 45, 30)
  Set pad = part.ShapeFactory.AddNewPad(sketch, 24)
  RequireSuccess "Create Pad_Chamfer_Base"
  pad.Name = "Pad_Chamfer_Base"
  part.UpdateObject pad
  RequireSuccess "Update Pad_Chamfer_Base"
  Set edgeBoundary = PadVerticalEdgeReference(partDoc, part, pad, sketch, 1, 2, "chamfer")
  WScript.Echo "[TOPOLOGY] stage=chamfer edgeType=" & ObjectTypeText(edgeBoundary) & _
    " edgeCATIAType=" & ObjectCATIAType(edgeBoundary) & _
    " selectionCount=" & SelectionCountText(partDoc.Selection) & _
    " inWorkObject=" & InWorkObjectText(part)
  DumpFeatureInventory partDoc, "chamfer before chamfer call"
  AssertPositiveVolume partDoc, "chamfer before chamfer call"

  beforeShapes = BodyShapesCount(body)
  Set chamfer = Nothing
  Err.Clear
  WScript.Echo "[FEATURE-CALL] case=chamfer stage=create method=AddNewChamfer" & _
    " beforeShapes=" & CStr(beforeShapes) & _
    " boundaryType=" & ObjectTypeText(edgeBoundary) & _
    " boundaryCATIAType=" & ObjectCATIAType(edgeBoundary) & _
    " propagation=" & CStr(CAT_TANGENCY_CHAMFER) & _
    " mode=" & CStr(CAT_LENGTH_ANGLE_CHAMFER) & _
    " orientation=" & CStr(CAT_NO_REVERSE_CHAMFER) & _
    " length=5 angle=45 inWorkObject=" & InWorkObjectText(part)
  On Error Resume Next
  Set chamfer = part.ShapeFactory.AddNewChamfer(edgeBoundary, CAT_TANGENCY_CHAMFER, CAT_LENGTH_ANGLE_CHAMFER, CAT_NO_REVERSE_CHAMFER, 5, 45)
  errNo = Err.Number
  errHex = Hex(Err.Number)
  errText = Err.Description
  errSource = Err.Source
  Err.Clear
  On Error GoTo 0
  afterShapes = BodyShapesCount(body)
  If errNo <> 0 Then
    WScript.Echo "[COM-ERROR] case=chamfer stage=create method=AddNewChamfer" & _
      " number=" & CStr(errNo) & " hex=0x" & errHex & _
      " description=" & Clean(errText) & " source=" & Clean(errSource) & _
      " returnedNothing=" & BoolText(chamfer Is Nothing) & _
      " beforeShapes=" & CStr(beforeShapes) & " afterShapes=" & CStr(afterShapes)
    DumpFeatureInventory partDoc, "chamfer COM failure after AddNewChamfer"
    FailCase "AddNewChamfer failed: " & errText, errNo, 10
  End If
  If chamfer Is Nothing Then
    WScript.Echo "[COM-ERROR] case=chamfer stage=create method=AddNewChamfer" & _
      " number=0 hex=0x0 description=CATIA returned Nothing" & _
      " beforeShapes=" & CStr(beforeShapes) & " afterShapes=" & CStr(afterShapes)
    DumpFeatureInventory partDoc, "chamfer returned Nothing after AddNewChamfer"
    FailCase "AddNewChamfer returned Nothing", 9023, 10
  End If
  WScript.Echo "[FEATURE] case=chamfer stage=create returnedType=" & ObjectTypeText(chamfer) & _
    " returnedCATIAType=" & ObjectCATIAType(chamfer) & _
    " beforeShapes=" & CStr(beforeShapes) & " afterShapes=" & CStr(afterShapes)
  If afterShapes <= beforeShapes Then
    DumpFeatureInventory partDoc, "chamfer shape count did not increase after factory call"
    FailCase "AddNewChamfer returned an object but Body.Shapes.Count did not increase", 9024, 10
  End If
  partDoc.Selection.Clear
  RequireObject chamfer, "length-angle chamfer factory result"
  RequireSuccess "Clear selection after chamfer"
  CommitNamedFeature part, chamfer, "Chamfer_LengthAngle", "length-angle chamfer"
  DumpFeatureInventory partDoc, "chamfer after update"
  AssertPositiveVolume partDoc, "chamfer after Chamfer_LengthAngle"
End Sub

Sub BuildShaftGroove(ByVal partDoc)
  Dim part, body, planeRef, sketch, f2d, shaft, axisLine
  Dim grooveSketch, groove, grooveAxisLine, angle1, angle2
  Dim beforeShapes, afterShapes, errNo, errHex, errText, errSource
  Set part = partDoc.Part
  Set body = MainBody(part)
  Set planeRef = part.CreateReferenceFromObject(part.OriginElements.PlaneZX)
  RequireSuccess "Reference PlaneZX"

  Set sketch = body.Sketches.Add(planeRef)
  RequireSuccess "Create Sketch_Shaft_Profile"
  sketch.Name = "Sketch_Shaft_Profile"
  Set f2d = sketch.OpenEdition()
  RequireSuccess "Open shaft sketch"
  f2d.CreateLine 10, 0, 35, 0
  f2d.CreateLine 35, 0, 35, 25
  f2d.CreateLine 35, 25, 10, 25
  f2d.CreateLine 10, 25, 10, 0
  Set axisLine = f2d.CreateLine(0, -10, 0, 35)
  WScript.Echo "[TOPOLOGY] stage=shaft axisLineType=" & ObjectTypeText(axisLine) & _
    " sketchType=" & ObjectTypeText(sketch) & " inWorkObject=" & InWorkObjectText(part)
  Err.Clear
  On Error Resume Next
  sketch.CenterLine = axisLine
  errNo = Err.Number
  errHex = Hex(Err.Number)
  errText = Err.Description
  errSource = Err.Source
  Err.Clear
  On Error GoTo 0
  If errNo <> 0 Then
    WScript.Echo "[COM-ERROR] case=shaft_groove stage=shaft method=Sketch.CenterLine" & _
      " number=" & CStr(errNo) & " hex=0x" & errHex & _
      " description=" & Clean(errText) & " source=" & Clean(errSource) & _
      " axisLineType=" & ObjectTypeText(axisLine)
    FailCase "Define shaft sketch CenterLine: " & errText, errNo, 10
  End If
  WScript.Echo "[FEATURE] case=shaft_groove stage=shaft centerLineType=" & ObjectTypeText(sketch.CenterLine)
  sketch.CloseEdition
  RequireSuccess "Close shaft sketch"
  beforeShapes = BodyShapesCount(body)
  Set shaft = Nothing
  Err.Clear
  WScript.Echo "[FEATURE-CALL] case=shaft_groove stage=shaft method=AddNewShaft" & _
    " beforeShapes=" & CStr(beforeShapes) & " sketchType=" & ObjectTypeText(sketch) & _
    " centerLineType=" & ObjectTypeText(sketch.CenterLine) & _
    " inWorkObject=" & InWorkObjectText(part)
  On Error Resume Next
  Set shaft = part.ShapeFactory.AddNewShaft(sketch)
  errNo = Err.Number
  errHex = Hex(Err.Number)
  errText = Err.Description
  errSource = Err.Source
  Err.Clear
  On Error GoTo 0
  afterShapes = BodyShapesCount(body)
  If errNo <> 0 Then
    WScript.Echo "[COM-ERROR] case=shaft_groove stage=shaft method=AddNewShaft" & _
      " number=" & CStr(errNo) & " hex=0x" & errHex & _
      " description=" & Clean(errText) & " source=" & Clean(errSource) & _
      " returnedNothing=" & BoolText(shaft Is Nothing) & _
      " beforeShapes=" & CStr(beforeShapes) & " afterShapes=" & CStr(afterShapes)
    DumpFeatureInventory partDoc, "shaft COM failure after AddNewShaft"
    FailCase "Create Shaft from sketch: " & errText, errNo, 10
  End If
  If shaft Is Nothing Then
    WScript.Echo "[COM-ERROR] case=shaft_groove stage=shaft method=AddNewShaft" & _
      " number=0 hex=0x0 description=CATIA returned Nothing" & _
      " beforeShapes=" & CStr(beforeShapes) & " afterShapes=" & CStr(afterShapes)
    DumpFeatureInventory partDoc, "shaft returned Nothing after AddNewShaft"
    FailCase "AddNewShaft returned Nothing", 9023, 10
  End If
  WScript.Echo "[FEATURE] case=shaft_groove stage=shaft returnedType=" & ObjectTypeText(shaft) & _
    " beforeShapes=" & CStr(beforeShapes) & " afterShapes=" & CStr(afterShapes)
  Set angle1 = shaft.FirstAngle: angle1.Value = 360
  Set angle2 = shaft.SecondAngle: angle2.Value = 0
  CommitNamedFeature part, shaft, "Shaft_Full360", "full 360-degree shaft"
  DumpFeatureInventory partDoc, "shaft after Shaft_Full360"
  AssertPositiveVolume partDoc, "after Shaft_Full360"

  Set grooveSketch = body.Sketches.Add(planeRef)
  RequireSuccess "Create Sketch_Groove_Profile"
  grooveSketch.Name = "Sketch_Groove_Profile"
  Set f2d = grooveSketch.OpenEdition()
  f2d.CreateLine 30, 8, 38, 8
  f2d.CreateLine 38, 8, 38, 15
  f2d.CreateLine 38, 15, 30, 15
  f2d.CreateLine 30, 15, 30, 8
  Set grooveAxisLine = f2d.CreateLine(0, -10, 0, 35)
  WScript.Echo "[TOPOLOGY] stage=groove axisLineType=" & ObjectTypeText(grooveAxisLine) & _
    " sketchType=" & ObjectTypeText(grooveSketch) & " inWorkObject=" & InWorkObjectText(part)
  Err.Clear
  On Error Resume Next
  grooveSketch.CenterLine = grooveAxisLine
  errNo = Err.Number
  errHex = Hex(Err.Number)
  errText = Err.Description
  errSource = Err.Source
  Err.Clear
  On Error GoTo 0
  If errNo <> 0 Then
    WScript.Echo "[COM-ERROR] case=shaft_groove stage=groove method=Sketch.CenterLine" & _
      " number=" & CStr(errNo) & " hex=0x" & errHex & _
      " description=" & Clean(errText) & " source=" & Clean(errSource) & _
      " axisLineType=" & ObjectTypeText(grooveAxisLine)
    FailCase "Define groove sketch CenterLine: " & errText, errNo, 10
  End If
  WScript.Echo "[FEATURE] case=shaft_groove stage=groove centerLineType=" & ObjectTypeText(grooveSketch.CenterLine)
  grooveSketch.CloseEdition
  RequireSuccess "Close groove sketch"
  beforeShapes = BodyShapesCount(body)
  Set groove = Nothing
  Err.Clear
  WScript.Echo "[FEATURE-CALL] case=shaft_groove stage=groove method=AddNewGroove" & _
    " beforeShapes=" & CStr(beforeShapes) & " sketchType=" & ObjectTypeText(grooveSketch) & _
    " centerLineType=" & ObjectTypeText(grooveSketch.CenterLine) & _
    " inWorkObject=" & InWorkObjectText(part)
  On Error Resume Next
  Set groove = part.ShapeFactory.AddNewGroove(grooveSketch)
  errNo = Err.Number
  errHex = Hex(Err.Number)
  errText = Err.Description
  errSource = Err.Source
  Err.Clear
  On Error GoTo 0
  afterShapes = BodyShapesCount(body)
  If errNo <> 0 Then
    WScript.Echo "[COM-ERROR] case=shaft_groove stage=groove method=AddNewGroove" & _
      " number=" & CStr(errNo) & " hex=0x" & errHex & _
      " description=" & Clean(errText) & " source=" & Clean(errSource) & _
      " returnedNothing=" & BoolText(groove Is Nothing) & _
      " beforeShapes=" & CStr(beforeShapes) & " afterShapes=" & CStr(afterShapes)
    DumpFeatureInventory partDoc, "groove COM failure after AddNewGroove"
    FailCase "Create Groove from sketch: " & errText, errNo, 10
  End If
  If groove Is Nothing Then
    WScript.Echo "[COM-ERROR] case=shaft_groove stage=groove method=AddNewGroove" & _
      " number=0 hex=0x0 description=CATIA returned Nothing" & _
      " beforeShapes=" & CStr(beforeShapes) & " afterShapes=" & CStr(afterShapes)
    DumpFeatureInventory partDoc, "groove returned Nothing after AddNewGroove"
    FailCase "AddNewGroove returned Nothing", 9023, 10
  End If
  WScript.Echo "[FEATURE] case=shaft_groove stage=groove returnedType=" & ObjectTypeText(groove) & _
    " beforeShapes=" & CStr(beforeShapes) & " afterShapes=" & CStr(afterShapes)
  Set angle1 = groove.FirstAngle: angle1.Value = 360
  Set angle2 = groove.SecondAngle: angle2.Value = 0
  CommitNamedFeature part, groove, "Groove_Annular360", "annular 360-degree groove"
  DumpFeatureInventory partDoc, "groove after Groove_Annular360"
  AssertPositiveVolume partDoc, "after Groove_Annular360"
End Sub

Sub BuildRibSlot(ByVal partDoc)
  Dim part, body, refXY, refYZ, profile, center, f2d, rib
  Dim slotProfile, slotCenter, slot
  Set part = partDoc.Part
  Set body = MainBody(part)
  Set refXY = part.CreateReferenceFromObject(part.OriginElements.PlaneXY)
  Set refYZ = part.CreateReferenceFromObject(part.OriginElements.PlaneYZ)
  RequireSuccess "Resolve rib/slot planes"

  Set profile = body.Sketches.Add(refYZ): profile.Name = "Sketch_Rib_Profile"
  Set f2d = profile.OpenEdition(): f2d.CreateClosedCircle 0, 0, 5: profile.CloseEdition
  RequireSuccess "Create rib profile"
  Set center = body.Sketches.Add(refXY): center.Name = "Sketch_Rib_Center"
  Set f2d = center.OpenEdition(): f2d.CreateLine 0, 0, 60, 0: center.CloseEdition
  RequireSuccess "Create rib center curve"
  Set rib = part.ShapeFactory.AddNewRib(profile, center)
  RequireSuccess "Create Rib_Straight"
  rib.Name = "Rib_Straight"
  part.UpdateObject rib
  RequireSuccess "Update Rib_Straight"

  Set slotProfile = body.Sketches.Add(refYZ): slotProfile.Name = "Sketch_Slot_Profile"
  Set f2d = slotProfile.OpenEdition(): f2d.CreateClosedCircle 0, 0, 2: slotProfile.CloseEdition
  RequireSuccess "Create slot profile"
  Set slotCenter = body.Sketches.Add(refXY): slotCenter.Name = "Sketch_Slot_Center"
  Set f2d = slotCenter.OpenEdition(): f2d.CreateLine 0, 0, 60, 0: slotCenter.CloseEdition
  RequireSuccess "Create slot center curve"
  Set slot = part.ShapeFactory.AddNewSlot(slotProfile, slotCenter)
  RequireSuccess "Create Slot_Straight"
  slot.Name = "Slot_Straight"
  part.UpdateObject slot
  RequireSuccess "Update Slot_Straight"
End Sub

Sub BuildShellThickness(ByVal partDoc)
  Dim part, body, planeRef, sketch, pad, faceBoundary, shell
  Dim thicknessBody, thicknessSketch, thicknessPad, thicknessBoundary, thickness
  Dim beforeShapes, afterShapes, errNo, errHex, errText, errSource
  Set part = partDoc.Part
  Set body = MainBody(part)
  Set planeRef = part.CreateReferenceFromObject(part.OriginElements.PlaneXY)
  Set sketch = RectSketch(body, planeRef, "Sketch_Shell_Base", -45, -35, 45, 35)
  Set pad = part.ShapeFactory.AddNewPad(sketch, 35)
  RequireSuccess "Create Pad_Shell_Base"
  pad.Name = "Pad_Shell_Base"
  part.UpdateObject pad
  RequireSuccess "Update Pad_Shell_Base"
  Set faceBoundary = PadFaceReference(partDoc, part, pad, 2, "shell")
  WScript.Echo "[TOPOLOGY] stage=shell faceType=" & ObjectTypeText(faceBoundary) & _
    " faceCATIAType=" & ObjectCATIAType(faceBoundary) & _
    " inWorkObject=" & InWorkObjectText(part)
  DumpFeatureInventory partDoc, "shell before shell call"
  AssertPositiveVolume partDoc, "shell before shell call"
  beforeShapes = BodyShapesCount(body)
  Set shell = Nothing
  Err.Clear
  WScript.Echo "[FEATURE-CALL] case=shell_thickness stage=shell method=AddNewShell" & _
    " beforeShapes=" & CStr(beforeShapes) & " faceType=" & ObjectTypeText(faceBoundary) & _
    " internalThickness=3 externalThickness=0 inWorkObject=" & InWorkObjectText(part)
  On Error Resume Next
  Set shell = part.ShapeFactory.AddNewShell(faceBoundary, 3, 0)
  errNo = Err.Number
  errHex = Hex(Err.Number)
  errText = Err.Description
  errSource = Err.Source
  Err.Clear
  On Error GoTo 0
  afterShapes = BodyShapesCount(body)
  If errNo <> 0 Then
    WScript.Echo "[COM-ERROR] case=shell_thickness stage=shell method=AddNewShell" & _
      " number=" & CStr(errNo) & " hex=0x" & errHex & _
      " description=" & Clean(errText) & " source=" & Clean(errSource) & _
      " returnedNothing=" & BoolText(shell Is Nothing) & _
      " beforeShapes=" & CStr(beforeShapes) & " afterShapes=" & CStr(afterShapes)
    DumpFeatureInventory partDoc, "shell COM failure after AddNewShell"
    FailCase "AddNewShell failed: " & errText, errNo, 10
  End If
  partDoc.Selection.Clear
  RequireObject shell, "shell factory result"
  RequireSuccess "Clear selection after Shell_3mm"
  CommitNamedFeature part, shell, "Shell_3mm", "3mm shell"
  DumpFeatureInventory partDoc, "shell after Shell_3mm"
  AssertPositiveVolume partDoc, "shell after Shell_3mm"

  ' Keep the local-thickness probe in a second native Body.  Applying a
  ' Thickness immediately after Shell makes the result depend on which wall
  ' R21 returned first; a separate solid still exercises the native decoder
  ' while remaining deterministic.
  Set thicknessBody = part.Bodies.Add()
  thicknessBody.Name = "Thickness_Test_Body"
  part.InWorkObject = thicknessBody
  Set thicknessSketch = RectSketch(thicknessBody, planeRef, "Sketch_Thickness_Base", 70, -25, 120, 25)
  Set thicknessPad = part.ShapeFactory.AddNewPad(thicknessSketch, 18)
  RequireObject thicknessPad, "thickness carrier pad result"
  thicknessPad.Name = "Pad_Thickness_Base"
  part.UpdateObject thicknessPad
  RequireSuccess "Update Pad_Thickness_Base"
  Set thicknessBoundary = PadFaceReference(partDoc, part, thicknessPad, 2, "thickness")
  WScript.Echo "[TOPOLOGY] stage=thickness faceType=" & ObjectTypeText(thicknessBoundary) & _
    " faceCATIAType=" & ObjectCATIAType(thicknessBoundary) & _
    " inWorkObject=" & InWorkObjectText(part)
  beforeShapes = BodyShapesCount(thicknessBody)
  Set thickness = Nothing
  Err.Clear
  WScript.Echo "[FEATURE-CALL] case=shell_thickness stage=thickness method=AddNewThickness" & _
    " beforeShapes=" & CStr(beforeShapes) & " faceType=" & ObjectTypeText(thicknessBoundary) & _
    " offset=1 inWorkObject=" & InWorkObjectText(part)
  On Error Resume Next
  Set thickness = part.ShapeFactory.AddNewThickness(thicknessBoundary, 1)
  errNo = Err.Number
  errHex = Hex(Err.Number)
  errText = Err.Description
  errSource = Err.Source
  Err.Clear
  On Error GoTo 0
  afterShapes = BodyShapesCount(thicknessBody)
  If errNo <> 0 Then
    WScript.Echo "[COM-ERROR] case=shell_thickness stage=thickness method=AddNewThickness" & _
      " number=" & CStr(errNo) & " hex=0x" & errHex & _
      " description=" & Clean(errText) & " source=" & Clean(errSource) & _
      " returnedNothing=" & BoolText(thickness Is Nothing) & _
      " beforeShapes=" & CStr(beforeShapes) & " afterShapes=" & CStr(afterShapes)
    DumpFeatureInventory partDoc, "thickness COM failure after AddNewThickness"
    FailCase "AddNewThickness failed: " & errText, errNo, 10
  End If
  partDoc.Selection.Clear
  RequireObject thickness, "local thickness factory result"
  RequireSuccess "Clear selection after Thickness"
  CommitNamedFeature part, thickness, "Thickness_Local1mm", "local 1mm thickness"
  DumpFeatureInventory partDoc, "thickness after Thickness_Local1mm"
End Sub

Sub BuildPattern(ByVal partDoc)
  Dim part, body, refXY, sketch, pad, seedSketch, seed, dir1, dir2, pattern
  Set part = partDoc.Part
  Set body = MainBody(part)
  Set refXY = part.CreateReferenceFromObject(part.OriginElements.PlaneXY)
  Set sketch = RectSketch(body, refXY, "Sketch_Pattern_Base", -70, -45, 70, 45)
  Set pad = part.ShapeFactory.AddNewPad(sketch, 12)
  RequireSuccess "Create Pad_Pattern_Base"
  pad.Name = "Pad_Pattern_Base"
  part.UpdateObject pad
  RequireSuccess "Update Pad_Pattern_Base"
  Set seedSketch = CircleSketch(body, refXY, "Sketch_Pattern_Seed", -45, -20, 6)
  Set seed = part.ShapeFactory.AddNewPad(seedSketch, 24)
  RequireSuccess "Create Pad_Pattern_Seed"
  seed.Name = "Pad_Pattern_Seed"
  part.UpdateObject seed
  RequireSuccess "Update Pad_Pattern_Seed"
  Set dir1 = part.CreateReferenceFromObject(part.OriginElements.PlaneYZ)
  Set dir2 = part.CreateReferenceFromObject(part.OriginElements.PlaneZX)
  RequireSuccess "Resolve rectangular-pattern directions"
  Set pattern = part.ShapeFactory.AddNewRectPattern(seed, 3, 2, 25, 25, 1, 1, dir1, dir2, False, False, 0)
  RequireSuccess "Create RectangularPattern_3x2"
  pattern.Name = "RectangularPattern_3x2"
  part.UpdateObject pattern
  RequireSuccess "Update RectangularPattern_3x2"
End Sub

Sub BuildBoolean(ByVal partDoc)
  Dim part, targetBody, toolBody, refXY, feature
  Set part = partDoc.Part
  Set refXY = part.CreateReferenceFromObject(part.OriginElements.PlaneXY)
  RequireSuccess "Reference PlaneXY for Boolean fixture"

  ' Use one independent result Body per Boolean kind.  Chaining Add, Remove,
  ' Assemble and Intersect on the same current result made R21's last update
  ' collapse the complete fixture to an empty body even though intermediate
  ' Product.Analyze values were stale and positive.
  Set targetBody = MainBody(part)
  AddBlockToBody part, targetBody, refXY, "Sketch_Boolean_Add_Target", -45, -30, 45, 30, 20, "Pad_Boolean_Add_Target"
  Set toolBody = AddToolBody(part, refXY, "ToolBody_Add", "Sketch_Tool_Add", 25, 0, 18, 30)
  part.InWorkObject = targetBody
  Set feature = part.ShapeFactory.AddNewAdd(toolBody): RequireSuccess "Create Boolean_Add"
  RequireObject feature, "Boolean_Add factory result"
  CommitNamedFeature part, feature, "Boolean_Add", "boolean add"
  AssertBodyPositiveVolume partDoc, targetBody, "after Boolean_Add"

  Set targetBody = part.Bodies.Add(): targetBody.Name = "Boolean_Remove_Result"
  AddBlockToBody part, targetBody, refXY, "Sketch_Boolean_Remove_Target", 75, -30, 165, 30, 20, "Pad_Boolean_Remove_Target"
  Set toolBody = AddToolBody(part, refXY, "ToolBody_Remove", "Sketch_Tool_Remove", 120, 0, 12, 30)
  part.InWorkObject = targetBody
  Set feature = part.ShapeFactory.AddNewRemove(toolBody): RequireSuccess "Create Boolean_Remove"
  RequireObject feature, "Boolean_Remove factory result"
  CommitNamedFeature part, feature, "Boolean_Remove", "boolean remove"
  AssertBodyPositiveVolume partDoc, targetBody, "after Boolean_Remove"

  Set targetBody = part.Bodies.Add(): targetBody.Name = "Boolean_Assemble_Result"
  AddBlockToBody part, targetBody, refXY, "Sketch_Boolean_Assemble_Target", -165, -30, -75, 30, 20, "Pad_Boolean_Assemble_Target"
  Set toolBody = AddToolBody(part, refXY, "ToolBody_Assemble", "Sketch_Tool_Assemble", -90, 0, 14, 30)
  part.InWorkObject = targetBody
  Set feature = part.ShapeFactory.AddNewAssemble(toolBody): RequireSuccess "Create Boolean_Assemble"
  RequireObject feature, "Boolean_Assemble factory result"
  CommitNamedFeature part, feature, "Boolean_Assemble", "boolean assemble"
  AssertBodyPositiveVolume partDoc, targetBody, "after Boolean_Assemble"

  Set targetBody = part.Bodies.Add(): targetBody.Name = "Boolean_Intersect_Result"
  AddBlockToBody part, targetBody, refXY, "Sketch_Boolean_Intersect_Target", -45, 70, 45, 130, 20, "Pad_Boolean_Intersect_Target"
  Set toolBody = AddToolBody(part, refXY, "ToolBody_Intersect", "Sketch_Tool_Intersect", 0, 100, 22, 30)
  part.InWorkObject = targetBody
  Set feature = part.ShapeFactory.AddNewIntersect(toolBody): RequireSuccess "Create Boolean_Intersect"
  RequireObject feature, "Boolean_Intersect factory result"
  CommitNamedFeature part, feature, "Boolean_Intersect", "boolean intersect"
  AssertBodyPositiveVolume partDoc, targetBody, "after Boolean_Intersect"
End Sub

Sub AddBlockToBody(ByVal part, ByVal body, ByVal planeRef, ByVal sketchName, ByVal x1, ByVal y1, ByVal x2, ByVal y2, ByVal height, ByVal padName)
  Dim sketch, pad
  part.InWorkObject = body
  Set sketch = RectSketch(body, planeRef, sketchName, x1, y1, x2, y2)
  Set pad = part.ShapeFactory.AddNewPad(sketch, height)
  RequireObject pad, padName & " factory result"
  RequireSuccess "Create " & padName
  pad.Name = padName
  part.UpdateObject pad
  RequireSuccess "Update " & padName
  part.Update
  RequireSuccess "Part.Update " & padName
End Sub

Function AddToolBody(ByVal part, ByVal planeRef, ByVal bodyName, ByVal sketchName, ByVal x, ByVal y, ByVal radius, ByVal height)
  Dim body, sketch, pad
  Set body = part.Bodies.Add(): body.Name = bodyName: part.InWorkObject = body
  Set sketch = CircleSketch(body, planeRef, sketchName, x, y, radius)
  Set pad = part.ShapeFactory.AddNewPad(sketch, height)
  RequireObject pad, bodyName & " pad factory result"
  RequireSuccess "Create pad in " & bodyName
  pad.Name = "Pad_" & bodyName
  part.UpdateObject pad
  RequireSuccess "Update " & bodyName
  part.Update
  RequireSuccess "Part.Update " & bodyName
  Set AddToolBody = body
End Function

Sub BuildGsdAnalytic(ByVal partDoc)
  Dim part, hybridBody, hsf, p1, p2, line, plane, axis
  Set part = partDoc.Part
  Set hybridBody = part.HybridBodies.Add(): hybridBody.Name = "GSD_Analytic"
  Set hsf = part.HybridShapeFactory
  Set p1 = hsf.AddNewPointCoord(0, 0, 0): p1.Name = "Point_Origin": hybridBody.AppendHybridShape p1
  Set p2 = hsf.AddNewPointCoord(50, 20, 30): p2.Name = "Point_End": hybridBody.AppendHybridShape p2
  RequireSuccess "Create GSD points"
  Set line = hsf.AddNewLinePtPt(part.CreateReferenceFromObject(p1), part.CreateReferenceFromObject(p2))
  RequireSuccess "Create GSD point-point line"
  line.Name = "Line_PointPoint": hybridBody.AppendHybridShape line
  Set plane = hsf.AddNewPlaneOffset(part.CreateReferenceFromObject(part.OriginElements.PlaneXY), 25, False)
  RequireSuccess "Create GSD offset plane"
  plane.Name = "Plane_Offset25": hybridBody.AppendHybridShape plane
  Set axis = part.AxisSystems.Add(): axis.Name = "AxisSystem_Test"
  RequireSuccess "Create AxisSystem_Test"
  part.Update
  RequireSuccess "Update GSD analytic part"
End Sub

Sub BuildPressure(ByVal partDoc)
  Dim part, body, refXY, sketch, pad, pocketSketch, pocket
  Dim edgeBoundary, fillet, chamferBoundary, chamfer
  Dim beforeShapes, afterShapes, errNo, errHex, errText, errSource
  Set part = partDoc.Part
  Set body = MainBody(part)
  Set refXY = part.CreateReferenceFromObject(part.OriginElements.PlaneXY)
  Set sketch = RectSketch(body, refXY, "Sketch_Pressure_Base", -55, -40, 55, 40)
  Set pad = part.ShapeFactory.AddNewPad(sketch, 25): RequireSuccess "Create Pad_Pressure"
  pad.Name = "Pad_Pressure": part.UpdateObject pad: RequireSuccess "Update Pad_Pressure"
  Set pocketSketch = CircleSketch(body, refXY, "Sketch_Pressure_Pocket", 0, 0, 15)
  Set pocket = part.ShapeFactory.AddNewPocket(pocketSketch, 10): RequireSuccess "Create Pocket_Pressure"
  pocket.Name = "Pocket_Pressure": pocket.DirectionOrientation = 0
  part.UpdateObject pocket: RequireSuccess "Update Pocket_Pressure"
  WScript.Echo "[STAGE] case=pressure stage=fillet_edge_ref"
  Set edgeBoundary = PressurePadEdgeReference(partDoc, part, pad, 1, 2, "pressure_fillet")
  WScript.Echo "[TOPOLOGY] stage=pressure_fillet edgeType=" & ObjectTypeText(edgeBoundary) & _
    " edgeCATIAType=" & ObjectCATIAType(edgeBoundary) & _
    " inWorkObject=" & InWorkObjectText(part)
  beforeShapes = BodyShapesCount(body)
  Set fillet = Nothing
  Err.Clear
  WScript.Echo "[FEATURE-CALL] case=pressure stage=fillet method=AddNewEdgeFilletWithConstantRadius" & _
    " beforeShapes=" & CStr(beforeShapes) & " boundaryType=" & ObjectTypeText(edgeBoundary) & _
    " radius=4 inWorkObject=" & InWorkObjectText(part)
  On Error Resume Next
  Set fillet = part.ShapeFactory.AddNewEdgeFilletWithConstantRadius(edgeBoundary, CAT_TANGENCY_FILLET, 4)
  errNo = Err.Number
  errHex = Hex(Err.Number)
  errText = Err.Description
  errSource = Err.Source
  Err.Clear
  On Error GoTo 0
  afterShapes = BodyShapesCount(body)
  If errNo <> 0 Then
    WScript.Echo "[COM-ERROR] case=pressure stage=fillet method=AddNewEdgeFilletWithConstantRadius" & _
      " number=" & CStr(errNo) & " hex=0x" & errHex & _
      " description=" & Clean(errText) & " source=" & Clean(errSource) & _
      " returnedNothing=" & BoolText(fillet Is Nothing) & _
      " beforeShapes=" & CStr(beforeShapes) & " afterShapes=" & CStr(afterShapes)
    DumpFeatureInventory partDoc, "pressure fillet COM failure"
    FailCase "Create Fillet_Pressure: " & errText, errNo, 10
  End If
  If fillet Is Nothing Then
    WScript.Echo "[COM-ERROR] case=pressure stage=fillet method=AddNewEdgeFilletWithConstantRadius number=0 hex=0x0 description=CATIA returned Nothing"
    DumpFeatureInventory partDoc, "pressure fillet returned Nothing"
    FailCase "AddNewEdgeFilletWithConstantRadius returned Nothing for pressure", 9023, 10
  End If
  WScript.Echo "[FEATURE] case=pressure stage=fillet returnedType=" & ObjectTypeText(fillet) & _
    " beforeShapes=" & CStr(beforeShapes) & " afterShapes=" & CStr(afterShapes)
  partDoc.Selection.Clear
  RequireObject fillet, "pressure fillet factory result"
  RequireSuccess "Clear selection after Fillet_Pressure"
  CommitNamedFeature part, fillet, "Fillet_Pressure", "pressure-part fillet"
  DumpFeatureInventory partDoc, "pressure after Fillet_Pressure"
  AssertPositiveVolume partDoc, "pressure after Fillet_Pressure"

  WScript.Echo "[STAGE] case=pressure stage=chamfer_edge_ref"
  Set chamferBoundary = PressurePadEdgeReference(partDoc, part, pad, 3, 4, "pressure_chamfer")
  WScript.Echo "[TOPOLOGY] stage=pressure_chamfer edgeType=" & ObjectTypeText(chamferBoundary) & _
    " edgeCATIAType=" & ObjectCATIAType(chamferBoundary) & _
    " inWorkObject=" & InWorkObjectText(part)
  beforeShapes = BodyShapesCount(body)
  Set chamfer = Nothing
  Err.Clear
  WScript.Echo "[FEATURE-CALL] case=pressure stage=chamfer method=AddNewChamfer" & _
    " beforeShapes=" & CStr(beforeShapes) & " boundaryType=" & ObjectTypeText(chamferBoundary) & _
    " propagation=" & CStr(CAT_TANGENCY_CHAMFER) & " mode=" & CStr(CAT_LENGTH_ANGLE_CHAMFER) & _
    " orientation=" & CStr(CAT_NO_REVERSE_CHAMFER) & " length=3 angle=45 inWorkObject=" & InWorkObjectText(part)
  On Error Resume Next
  Set chamfer = part.ShapeFactory.AddNewChamfer(chamferBoundary, CAT_TANGENCY_CHAMFER, CAT_LENGTH_ANGLE_CHAMFER, CAT_NO_REVERSE_CHAMFER, 3, 45)
  errNo = Err.Number
  errHex = Hex(Err.Number)
  errText = Err.Description
  errSource = Err.Source
  Err.Clear
  On Error GoTo 0
  afterShapes = BodyShapesCount(body)
  If errNo <> 0 Then
    WScript.Echo "[COM-ERROR] case=pressure stage=chamfer method=AddNewChamfer" & _
      " number=" & CStr(errNo) & " hex=0x" & errHex & _
      " description=" & Clean(errText) & " source=" & Clean(errSource) & _
      " returnedNothing=" & BoolText(chamfer Is Nothing) & _
      " beforeShapes=" & CStr(beforeShapes) & " afterShapes=" & CStr(afterShapes)
    DumpFeatureInventory partDoc, "pressure chamfer COM failure"
    FailCase "Create Chamfer_Pressure: " & errText, errNo, 10
  End If
  If chamfer Is Nothing Then
    WScript.Echo "[COM-ERROR] case=pressure stage=chamfer method=AddNewChamfer number=0 hex=0x0 description=CATIA returned Nothing"
    DumpFeatureInventory partDoc, "pressure chamfer returned Nothing"
    FailCase "AddNewChamfer returned Nothing for pressure", 9023, 10
  End If
  WScript.Echo "[FEATURE] case=pressure stage=chamfer returnedType=" & ObjectTypeText(chamfer) & _
    " beforeShapes=" & CStr(beforeShapes) & " afterShapes=" & CStr(afterShapes)
  partDoc.Selection.Clear
  RequireObject chamfer, "pressure chamfer factory result"
  RequireSuccess "Clear selection after Chamfer_Pressure"
  CommitNamedFeature part, chamfer, "Chamfer_Pressure", "pressure-part chamfer"
  DumpFeatureInventory partDoc, "pressure after Chamfer_Pressure"
  AssertPositiveVolume partDoc, "pressure after Chamfer_Pressure"
End Sub

Function TopologyBoundary(ByVal partDoc, ByVal topologyKind, ByVal supportShape, ByVal prompt)
  Dim sel, boundary, countValue, status, filters(0), query, sourceText
  Dim errNo, errHex, errText, errSource
  Set boundary = Nothing
  Set sel = partDoc.Selection
  sel.Clear
  partDoc.Activate
  catia.Visible = True

  If Not guidedMode Then
    ' Restrict the search to the feature that owns the desired result first.
    ' This avoids accidentally taking a sketch edge or a boundary from another
    ' Body in the multi-body fixtures.
    Err.Clear
    On Error Resume Next
    sel.Add supportShape
    errNo = Err.Number
    errHex = Hex(Err.Number)
    errText = Err.Description
    errSource = Err.Source
    Err.Clear
    On Error GoTo 0
    If errNo <> 0 Then
      WScript.Echo "[COM-ERROR] stage=topology method=Selection.Add" & _
        " number=" & CStr(errNo) & " hex=0x" & errHex & _
        " description=" & Clean(errText) & " source=" & Clean(errSource) & _
        " supportType=" & ObjectTypeText(supportShape)
      FailCase "Seed feature-scoped topology search failed: " & errText, errNo, 10
    End If
    query = "Topology.CAT" & topologyKind & ",sel"
    Err.Clear
    On Error Resume Next
    sel.Search query
    errNo = Err.Number
    errHex = Hex(Err.Number)
    errText = Err.Description
    errSource = Err.Source
    Err.Clear
    On Error GoTo 0
    If errNo = 0 Then
      countValue = 0
      Err.Clear
      On Error Resume Next
      countValue = sel.Count2
      If Err.Number <> 0 Then Err.Clear: countValue = sel.Count
      errNo = Err.Number
      errHex = Hex(Err.Number)
      errText = Err.Description
      errSource = Err.Source
      Err.Clear
      On Error GoTo 0
      If errNo <> 0 Then
        WScript.Echo "[COM-ERROR] stage=topology method=Selection.Count/Count2 query=" & query & _
          " number=" & CStr(errNo) & " hex=0x" & errHex & _
          " description=" & Clean(errText) & " source=" & Clean(errSource)
        countValue = 0
      End If
      If countValue > 0 Then
        Err.Clear
        On Error Resume Next
        Set boundary = sel.Item2(1).Value
        If Err.Number <> 0 Or boundary Is Nothing Then
          Err.Clear
          Set boundary = sel.Item(1).Value
        End If
        errNo = Err.Number
        errHex = Hex(Err.Number)
        errText = Err.Description
        errSource = Err.Source
        Err.Clear
        On Error GoTo 0
        If errNo <> 0 Then
          WScript.Echo "[COM-ERROR] stage=topology method=Selection.Item query=" & query & _
            " number=" & CStr(errNo) & " hex=0x" & errHex & _
            " description=" & Clean(errText) & " source=" & Clean(errSource)
          Set boundary = Nothing
        End If
        sourceText = "feature-scoped"
      End If
    Else
      WScript.Echo "[COM-ERROR] stage=topology method=Selection.Search query=" & query & _
        " number=" & CStr(errNo) & " hex=0x" & errHex & _
        " description=" & Clean(errText) & " source=" & Clean(errSource) & _
        " fallback=document-wide"
    End If
    Err.Clear

    ' Some R21 installations do not honor the ,sel topology scope.  Fall back
    ' to all topology only if the scoped search returned nothing.
    If boundary Is Nothing Then
      sel.Clear
      query = "Topology.CAT" & topologyKind & ",all"
      Err.Clear
      On Error Resume Next
      sel.Search query
      errNo = Err.Number
      errHex = Hex(Err.Number)
      errText = Err.Description
      errSource = Err.Source
      Err.Clear
      On Error GoTo 0
      If errNo = 0 Then
        countValue = 0
        Err.Clear
        On Error Resume Next
        countValue = sel.Count2
        If Err.Number <> 0 Then Err.Clear: countValue = sel.Count
        errNo = Err.Number
        errHex = Hex(Err.Number)
        errText = Err.Description
        errSource = Err.Source
        Err.Clear
        On Error GoTo 0
        If errNo <> 0 Then
          WScript.Echo "[COM-ERROR] stage=topology method=Selection.Count/Count2 query=" & query & _
            " number=" & CStr(errNo) & " hex=0x" & errHex & _
            " description=" & Clean(errText) & " source=" & Clean(errSource)
          countValue = 0
        End If
        If countValue > 0 Then
          Err.Clear
          On Error Resume Next
          Set boundary = sel.Item2(1).Value
          If Err.Number <> 0 Or boundary Is Nothing Then
            Err.Clear
            Set boundary = sel.Item(1).Value
          End If
          errNo = Err.Number
          errHex = Hex(Err.Number)
          errText = Err.Description
          errSource = Err.Source
          Err.Clear
          On Error GoTo 0
          If errNo <> 0 Then
            WScript.Echo "[COM-ERROR] stage=topology method=Selection.Item query=" & query & _
              " number=" & CStr(errNo) & " hex=0x" & errHex & _
              " description=" & Clean(errText) & " source=" & Clean(errSource)
            Set boundary = Nothing
          End If
          sourceText = "document-wide"
        End If
      Else
        WScript.Echo "[COM-ERROR] stage=topology method=Selection.Search query=" & query & _
          " number=" & CStr(errNo) & " hex=0x" & errHex & _
          " description=" & Clean(errText) & " source=" & Clean(errSource)
      End If
      Err.Clear
    End If
  End If

  If boundary Is Nothing And Not guidedMode Then
    WScript.Echo "[COM-ERROR] stage=topology method=TopologyBoundary" & _
      " number=0 hex=0x0 description=no automatic " & topologyKind & _
      " boundary found; guided mode required for interactive selection" & _
      " selectionCount=" & SelectionCountText(sel)
    DumpFeatureInventory partDoc, "no automatic " & topologyKind & " boundary"
    FailCase "No automatic " & topologyKind & " boundary found; rerun this case with guided mode for manual selection", 9011, 10
  End If

  If boundary Is Nothing Then
    sel.Clear
    If topologyKind = "Edge" Then
      filters(0) = "TriDimFeatEdge"
    Else
      filters(0) = "Face"
    End If
    WScript.Echo "[SELECT] " & prompt
    Err.Clear
    status = sel.SelectElement2(filters, prompt, False)
    RequireSuccess "Interactive " & topologyKind & " selection"
    If status <> "Normal" Then FailCase "Selection cancelled: " & prompt, 9010, 10
    Err.Clear
    Set boundary = sel.Item2(1).Value
    If Err.Number <> 0 Or boundary Is Nothing Then
      Err.Clear
      Set boundary = sel.Item(1).Value
    End If
    RequireSuccess "Read selected " & topologyKind & " boundary"
    sourceText = "interactive"
  End If
  If boundary Is Nothing Then FailCase "No usable " & topologyKind & " boundary", 9011, 10
  ' Do not clear Selection here.  CATIA Boundary objects are short-lived; the
  ' caller clears it only after the ShapeFactory method has consumed Value.
  WScript.Echo "[TOPOLOGY] " & topologyKind & " source=" & sourceText & " type=" & TypeName(boundary)
  Set TopologyBoundary = boundary
End Function

Function PadVerticalEdgeReference(ByVal partDoc, ByVal part, ByVal pad, ByVal sketch, ByVal firstLine, ByVal secondLine, ByVal stageName)
  Dim padName, sketchName, label, edgeRef, errNo, errHex, errText, errSource
  padName = ObjectNameText(pad)
  sketchName = ObjectNameText(sketch)
  If stageName = "fillet" Or stageName = "chamfer" Or stageName = "pressure_fillet" Or stageName = "pressure_chamfer" Then
    padName = "Pad.1"
    sketchName = "Sketch.1"
  End If
  label = "REdge:(Edge:(Face:(Brp:(" & padName & ";0:(Brp:(" & sketchName & ";" & CStr(firstLine) & ")));None:());" & _
    "Face:(Brp:(" & padName & ";0:(Brp:(" & sketchName & ";" & CStr(secondLine) & ")));None:());" & _
    "None:(Limits1:();Limits2:()));WithTemporaryBody;WithoutBuildError;WithSelectingFeatureSupport)"

  WScript.Echo "[TOPOLOGY] stage=" & stageName & " method=CreateReferenceFromBRepName" & _
    " pad=" & padName & " sketch=" & sketchName & _
    " firstLine=" & CStr(firstLine) & " secondLine=" & CStr(secondLine)
  Set edgeRef = Nothing
  Err.Clear
  On Error Resume Next
  Set edgeRef = part.CreateReferenceFromBRepName(label, pad)
  errNo = Err.Number
  errHex = Hex(Err.Number)
  errText = Err.Description
  errSource = Err.Source
  Err.Clear
  On Error GoTo 0
  If errNo <> 0 Then
    WScript.Echo "[COM-ERROR] stage=" & stageName & " method=CreateReferenceFromBRepName" & _
      " number=" & CStr(errNo) & " hex=0x" & errHex & _
      " description=" & Clean(errText) & " source=" & Clean(errSource) & _
      " label=" & label
    DumpFeatureInventory partDoc, stageName & " BRep edge reference failure"
    FailCase "CreateReferenceFromBRepName failed for " & stageName & " edge: " & errText, errNo, 10
  End If
  If edgeRef Is Nothing Then
    WScript.Echo "[COM-ERROR] stage=" & stageName & " method=CreateReferenceFromBRepName" & _
      " number=0 hex=0x0 description=CATIA returned Nothing label=" & label
    DumpFeatureInventory partDoc, stageName & " BRep edge reference returned Nothing"
    FailCase "CreateReferenceFromBRepName returned Nothing for " & stageName & " edge", 9023, 10
  End If
  Set PadVerticalEdgeReference = edgeRef
End Function

Function PressurePadEdgeReference(ByVal partDoc, ByVal part, ByVal pad, ByVal firstLine, ByVal secondLine, ByVal stageName)
  Dim label, edgeRef, errNo, errHex, errText, errSource
  label = "REdge:(Edge:(Face:(Brp:(Pad.1;0:(Brp:(Sketch.1;" & CStr(firstLine) & ")));None:());" & _
    "Face:(Brp:(Pad.1;0:(Brp:(Sketch.1;" & CStr(secondLine) & ")));None:());" & _
    "None:(Limits1:();Limits2:()));WithTemporaryBody;WithoutBuildError;WithSelectingFeatureSupport)"
  WScript.Echo "[TOPOLOGY] stage=" & stageName & " method=CreateReferenceFromBRepName pad=Pad.1 sketch=Sketch.1 firstLine=" & CStr(firstLine) & " secondLine=" & CStr(secondLine)
  Set edgeRef = Nothing
  Err.Clear
  On Error Resume Next
  Set edgeRef = part.CreateReferenceFromBRepName(label, pad)
  errNo = Err.Number
  errHex = Hex(Err.Number)
  errText = Err.Description
  errSource = Err.Source
  Err.Clear
  On Error GoTo 0
  If errNo <> 0 Then
    WScript.Echo "[COM-ERROR] stage=" & stageName & " method=CreateReferenceFromBRepName" & _
      " number=" & CStr(errNo) & " hex=0x" & errHex & _
      " description=" & Clean(errText) & " source=" & Clean(errSource) & _
      " label=" & label
    DumpFeatureInventory partDoc, stageName & " pressure edge reference failure"
    FailCase "CreateReferenceFromBRepName failed for " & stageName & " edge: " & errText, errNo, 10
  End If
  If edgeRef Is Nothing Then
    WScript.Echo "[COM-ERROR] stage=" & stageName & " method=CreateReferenceFromBRepName number=0 hex=0x0 description=CATIA returned Nothing label=" & label
    DumpFeatureInventory partDoc, stageName & " pressure edge reference returned Nothing"
    FailCase "CreateReferenceFromBRepName returned Nothing for " & stageName & " edge", 9023, 10
  End If
  Set PressurePadEdgeReference = edgeRef
End Function

Function AxisReferenceFromLine(ByVal partDoc, ByVal part, ByVal lineObj, ByVal stageName)
  Dim axisRef, errNo, errHex, errText, errSource
  Set axisRef = Nothing
  Err.Clear
  WScript.Echo "[TOPOLOGY] stage=" & stageName & " method=CreateReferenceFromObject axisLineType=" & ObjectTypeText(lineObj)
  On Error Resume Next
  Set axisRef = part.CreateReferenceFromObject(lineObj)
  errNo = Err.Number
  errHex = Hex(Err.Number)
  errText = Err.Description
  errSource = Err.Source
  Err.Clear
  On Error GoTo 0
  If errNo <> 0 Then
    WScript.Echo "[COM-ERROR] stage=" & stageName & " method=CreateReferenceFromObject(axisLine)" & _
      " number=" & CStr(errNo) & " hex=0x" & errHex & _
      " description=" & Clean(errText) & " source=" & Clean(errSource)
    DumpFeatureInventory partDoc, stageName & " axis reference failure"
    FailCase "CreateReferenceFromObject failed for " & stageName & " axis: " & errText, errNo, 10
  End If
  If axisRef Is Nothing Then
    WScript.Echo "[COM-ERROR] stage=" & stageName & " method=CreateReferenceFromObject(axisLine)" & _
      " number=0 hex=0x0 description=CATIA returned Nothing"
    DumpFeatureInventory partDoc, stageName & " axis reference returned Nothing"
    FailCase "CreateReferenceFromObject returned Nothing for " & stageName & " axis", 9023, 10
  End If
  Set AxisReferenceFromLine = axisRef
End Function

Function PadFaceReference(ByVal partDoc, ByVal part, ByVal pad, ByVal faceIndex, ByVal stageName)
  Dim padName, label, faceRef, errNo, errHex, errText, errSource
  padName = ObjectNameText(pad)
  If stageName = "shell" Then padName = "Pad.1"
  If stageName = "thickness" Then padName = "Pad.2"
  label = "RSur:(Face:(Brp:(" & padName & ";" & CStr(faceIndex) & ");None:());WithTemporaryBody;WithoutBuildError;WithSelectingFeatureSupport)"
  WScript.Echo "[TOPOLOGY] stage=" & stageName & " method=CreateReferenceFromBRepName pad=" & padName & " faceIndex=" & CStr(faceIndex)
  Set faceRef = Nothing
  Err.Clear
  On Error Resume Next
  Set faceRef = part.CreateReferenceFromBRepName(label, pad)
  errNo = Err.Number
  errHex = Hex(Err.Number)
  errText = Err.Description
  errSource = Err.Source
  Err.Clear
  On Error GoTo 0
  If errNo <> 0 Then
    WScript.Echo "[COM-ERROR] stage=" & stageName & " method=CreateReferenceFromBRepName" & _
      " number=" & CStr(errNo) & " hex=0x" & errHex & _
      " description=" & Clean(errText) & " source=" & Clean(errSource) & _
      " label=" & label
    DumpFeatureInventory partDoc, stageName & " BRep face reference failure"
    FailCase "CreateReferenceFromBRepName failed for " & stageName & " face: " & errText, errNo, 10
  End If
  If faceRef Is Nothing Then
    WScript.Echo "[COM-ERROR] stage=" & stageName & " method=CreateReferenceFromBRepName" & _
      " number=0 hex=0x0 description=CATIA returned Nothing label=" & label
    DumpFeatureInventory partDoc, stageName & " BRep face reference returned Nothing"
    FailCase "CreateReferenceFromBRepName returned Nothing for " & stageName & " face", 9023, 10
  End If
  Set PadFaceReference = faceRef
End Function

Function MainBody(ByVal part)
  Dim body
  Err.Clear
  If part.Bodies.Count = 0 Then
    Set body = part.Bodies.Add()
  Else
    Set body = part.Bodies.Item(1)
  End If
  RequireSuccess "Resolve PartBody"
  body.Name = "PartBody"
  part.InWorkObject = body
  Set MainBody = body
End Function

Function RectSketch(ByVal body, ByVal supportRef, ByVal sketchName, ByVal x1, ByVal y1, ByVal x2, ByVal y2)
  Dim sketch, f2d
  Err.Clear
  Set sketch = body.Sketches.Add(supportRef)
  RequireSuccess "Create " & sketchName
  sketch.Name = sketchName
  Set f2d = sketch.OpenEdition()
  RequireSuccess "Open " & sketchName
  f2d.CreateLine x1, y1, x2, y1
  f2d.CreateLine x2, y1, x2, y2
  f2d.CreateLine x2, y2, x1, y2
  f2d.CreateLine x1, y2, x1, y1
  sketch.CloseEdition
  RequireSuccess "Close " & sketchName
  Set RectSketch = sketch
End Function

Function CircleSketch(ByVal body, ByVal supportRef, ByVal sketchName, ByVal x, ByVal y, ByVal radius)
  Dim sketch, f2d
  Err.Clear
  Set sketch = body.Sketches.Add(supportRef)
  RequireSuccess "Create " & sketchName
  sketch.Name = sketchName
  Set f2d = sketch.OpenEdition()
  RequireSuccess "Open " & sketchName
  f2d.CreateClosedCircle x, y, radius
  sketch.CloseEdition
  RequireSuccess "Close " & sketchName
  Set CircleSketch = sketch
End Function

Sub CommitNamedFeature(ByVal part, ByVal feature, ByVal targetName, ByVal stepName)
  Dim errNo, errHex, errText, errSource
  RequireObject feature, stepName & " object before update"
  Err.Clear
  On Error Resume Next
  part.UpdateObject feature
  errNo = Err.Number
  errHex = Hex(Err.Number)
  errText = Err.Description
  errSource = Err.Source
  Err.Clear
  On Error GoTo 0
  If errNo <> 0 Then
    WScript.Echo "[UPDATE-ERROR] feature=" & stepName & " method=Part.UpdateObject" & _
      " number=" & CStr(errNo) & " hex=0x" & errHex & _
      " description=" & Clean(errText) & " source=" & Clean(errSource) & _
      " featureType=" & ObjectTypeText(feature) & " featureCATIAType=" & ObjectCATIAType(feature) & _
      " inWorkObject=" & InWorkObjectText(part)
    FailCase "Update " & stepName & ": " & errText, errNo, 10
  End If
  Err.Clear
  On Error Resume Next
  feature.Name = targetName
  errNo = Err.Number
  errHex = Hex(Err.Number)
  errText = Err.Description
  errSource = Err.Source
  Err.Clear
  On Error GoTo 0
  If errNo <> 0 Then
    WScript.Echo "[COM-ERROR] feature=" & stepName & " method=Name" & _
      " number=" & CStr(errNo) & " hex=0x" & errHex & _
      " description=" & Clean(errText) & " source=" & Clean(errSource) & _
      " targetName=" & targetName
    FailCase "Name " & stepName & " as " & targetName & ": " & errText, errNo, 10
  End If
  Err.Clear
  On Error Resume Next
  part.UpdateObject feature
  errNo = Err.Number
  errHex = Hex(Err.Number)
  errText = Err.Description
  errSource = Err.Source
  Err.Clear
  On Error GoTo 0
  If errNo <> 0 Then
    WScript.Echo "[UPDATE-ERROR] feature=" & targetName & " method=Part.UpdateObject" & _
      " number=" & CStr(errNo) & " hex=0x" & errHex & _
      " description=" & Clean(errText) & " source=" & Clean(errSource) & _
      " featureType=" & ObjectTypeText(feature) & " featureCATIAType=" & ObjectCATIAType(feature) & _
      " inWorkObject=" & InWorkObjectText(part)
    FailCase "Re-update " & stepName & ": " & errText, errNo, 10
  End If
  ' Some R21 dress-up/boolean features re-apply their default label during Update.
  ' Write the user-visible name again after the final update, immediately before SaveAs.
  Err.Clear
  On Error Resume Next
  feature.Name = targetName
  errNo = Err.Number
  errHex = Hex(Err.Number)
  errText = Err.Description
  errSource = Err.Source
  Err.Clear
  On Error GoTo 0
  If errNo <> 0 Then
    WScript.Echo "[COM-ERROR] feature=" & stepName & " method=NamePersist" & _
      " number=" & CStr(errNo) & " hex=0x" & errHex & _
      " description=" & Clean(errText) & " source=" & Clean(errSource) & _
      " targetName=" & targetName
    FailCase "Persist name " & targetName & ": " & errText, errNo, 10
  End If
  WScript.Echo "[FEATURE] " & targetName & " type=" & TypeName(feature)
End Sub

Sub VerifyNames(ByVal partDoc, ByVal names, ByVal context)
  Dim i, obj, part
  Set part = partDoc.Part
  For i = 0 To UBound(names)
    Set obj = FindHistoryObject(partDoc, CStr(names(i)))
    If obj Is Nothing Then
      DumpFeatureInventory partDoc, "missing " & CStr(names(i)) & " " & context
      FailCase "Missing expected native history object " & context & ": " & names(i), 9020, 20
    End If
    WScript.Echo "[HISTORY-OK] " & context & " " & CStr(names(i)) & " type=" & TypeName(obj)
  Next
End Sub

Function FindHistoryObject(ByVal partDoc, ByVal expectedName)
  Dim part, obj, sel, countValue, query
  Set FindHistoryObject = Nothing
  Set part = partDoc.Part
  Set obj = Nothing
  Err.Clear
  Set obj = part.FindObjectByName(expectedName)
  If Err.Number = 0 And Not obj Is Nothing Then
    Set FindHistoryObject = obj
    Exit Function
  End If

  ' FindObjectByName is inconsistent for several dress-up features in old V5.
  ' Search by the specification-tree display name as a second, independent check.
  Err.Clear
  Set sel = partDoc.Selection
  sel.Clear
  query = "Name=" & expectedName & ",all"
  sel.Search query
  If Err.Number = 0 Then
    countValue = 0
    countValue = sel.Count2
    If Err.Number <> 0 Then Err.Clear: countValue = sel.Count
    If countValue > 0 Then
      Err.Clear
      Set obj = sel.Item2(1).Value
      If Err.Number <> 0 Or obj Is Nothing Then
        Err.Clear
        Set obj = sel.Item(1).Value
      End If
    End If
  End If
  sel.Clear
  Err.Clear
  If Not obj Is Nothing Then Set FindHistoryObject = obj
End Function

Function ObjectTypeText(ByVal obj)
  On Error Resume Next
  ObjectTypeText = TypeName(obj)
  If Err.Number <> 0 Then
    ObjectTypeText = "<type-error 0x" & Hex(Err.Number) & " " & Clean(Err.Description) & ">"
    Err.Clear
  End If
  On Error GoTo 0
End Function

Function ObjectCATIAType(ByVal obj)
  On Error Resume Next
  ObjectCATIAType = obj.CATIAType
  If Err.Number <> 0 Then
    ObjectCATIAType = "<no-CATIAType 0x" & Hex(Err.Number) & ">"
    Err.Clear
  End If
  On Error GoTo 0
End Function

Function ObjectNameText(ByVal obj)
  On Error Resume Next
  ObjectNameText = obj.Name
  If Err.Number <> 0 Then
    ObjectNameText = "<no-name 0x" & Hex(Err.Number) & ">"
    Err.Clear
  End If
  On Error GoTo 0
End Function

Function InWorkObjectText(ByVal part)
  Dim obj
  On Error Resume Next
  Set obj = part.InWorkObject
  If Err.Number <> 0 Or obj Is Nothing Then
    InWorkObjectText = "<unavailable 0x" & Hex(Err.Number) & " " & Clean(Err.Description) & ">"
    Err.Clear
  Else
    InWorkObjectText = ObjectNameText(obj) & "/" & ObjectTypeText(obj) & "/" & ObjectCATIAType(obj)
  End If
  On Error GoTo 0
End Function

Function SelectionCountText(ByVal sel)
  Dim c1, c2, e1, e2
  On Error Resume Next
  c1 = sel.Count
  e1 = Err.Number
  Err.Clear
  c2 = sel.Count2
  e2 = Err.Number
  Err.Clear
  On Error GoTo 0
  If e1 <> 0 Then c1 = "<err 0x" & Hex(e1) & ">"
  If e2 <> 0 Then c2 = "<err 0x" & Hex(e2) & ">"
  SelectionCountText = "Count=" & CStr(c1) & "/Count2=" & CStr(c2)
End Function

Function BodyShapesCount(ByVal body)
  On Error Resume Next
  BodyShapesCount = body.Shapes.Count
  If Err.Number <> 0 Then
    BodyShapesCount = -1
    Err.Clear
  End If
  On Error GoTo 0
End Function

Function BoolText(ByVal value)
  If value Then BoolText = "true" Else BoolText = "false"
End Function

Sub DumpFeatureInventory(ByVal partDoc, ByVal reason)
  Dim part, bodies, body, shapes, feature, i, j, featureName
  On Error Resume Next
  Set part = partDoc.Part
  WScript.Echo "[HISTORY-DUMP] " & reason
  Set bodies = part.Bodies
  For i = 1 To bodies.Count
    Set body = bodies.Item(i)
    WScript.Echo "[HISTORY] BODY " & body.Name & " type=" & TypeName(body)
    Set shapes = Nothing
    Err.Clear
    Set shapes = body.Shapes
    If Err.Number = 0 And Not shapes Is Nothing Then
      For j = 1 To shapes.Count
        Set feature = Nothing
        Set feature = shapes.Item(j)
        featureName = "<unreadable>"
        Err.Clear
        featureName = feature.Name
        If Err.Number <> 0 Then Err.Clear
        WScript.Echo "[HISTORY]   " & CStr(j) & " " & featureName & " type=" & TypeName(feature)
      Next
    End If
    Err.Clear
  Next
  Err.Clear
End Sub

Sub AssertPositiveVolume(ByVal partDoc, ByVal context)
  Dim volume, spaVolume, spa, bodyRef, measurable, mainResult
  volume = 0
  spaVolume = 0
  Err.Clear
  volume = partDoc.Product.Analyze.Volume
  If Err.Number <> 0 Then Err.Clear: volume = 0
  If volume > 0 Then Exit Sub

  ' Product.Analyze can report zero on an unsaved multi-body R21 document.
  ' Re-check the Part's main result with the independent SPA workbench.
  Set spa = Nothing
  Set mainResult = Nothing
  Set bodyRef = Nothing
  Set measurable = Nothing
  Err.Clear
  Set spa = partDoc.GetWorkbench("SPAWorkbench")
  Set mainResult = partDoc.Part.MainBody
  Set bodyRef = partDoc.Part.CreateReferenceFromObject(mainResult)
  Set measurable = spa.GetMeasurable(bodyRef)
  spaVolume = measurable.Volume
  If Err.Number <> 0 Then Err.Clear: spaVolume = 0
  If spaVolume > 0 Then
    WScript.Echo "[VOLUME] " & context & " Product.Analyze=0 SPA.MainBody=" & CStr(spaVolume)
    Exit Sub
  End If

  DumpFeatureInventory partDoc, "zero volume in " & context
  FailCase "No positive volume in " & context & " (Product.Analyze=" & CStr(volume) & ", SPA.MainBody=" & CStr(spaVolume) & ")", 9021, 21
End Sub

Sub AssertBodyPositiveVolume(ByVal partDoc, ByVal body, ByVal context)
  Dim spa, bodyRef, measurable, bodyVolume
  bodyVolume = 0
  Set spa = Nothing
  Set bodyRef = Nothing
  Set measurable = Nothing
  Err.Clear
  Set spa = partDoc.GetWorkbench("SPAWorkbench")
  Set bodyRef = partDoc.Part.CreateReferenceFromObject(body)
  Set measurable = spa.GetMeasurable(bodyRef)
  bodyVolume = measurable.Volume
  If Err.Number <> 0 Then Err.Clear: bodyVolume = 0
  WScript.Echo "[BODY-VOLUME] " & context & " body=" & body.Name & " volume=" & CStr(bodyVolume)
  If bodyVolume <= 0 Then
    DumpFeatureInventory partDoc, "zero body volume " & context
    FailCase "No positive result volume " & context & " body=" & body.Name, 9022, 22
  End If
End Sub

Sub BackupExisting(ByVal path)
  Dim backupRoot, backupDir, backupPath
  If Not fso.FileExists(path) Then Exit Sub
  backupRoot = fso.BuildPath(outputDir, "repair_backups")
  EnsureFolder backupRoot
  backupDir = fso.BuildPath(backupRoot, Stamp())
  EnsureFolder backupDir
  backupPath = fso.BuildPath(backupDir, fso.GetFileName(path))
  Err.Clear
  fso.CopyFile path, backupPath, True
  RequireSuccess "Backup existing fixture"
  WScript.Echo "[BACKUP] " & backupPath
End Sub

Function Stamp()
  Dim value
  value = Year(Now) & Two(Month(Now)) & Two(Day(Now)) & "_" & Two(Hour(Now)) & Two(Minute(Now)) & Two(Second(Now))
  Stamp = value
End Function

Function Two(ByVal value)
  If value < 10 Then Two = "0" & value Else Two = CStr(value)
End Function

Function ModeText()
  If guidedMode Then ModeText = "guided-selection" Else ModeText = "auto-topology-search"
End Function

Sub EnsureFolder(ByVal path)
  Dim parent
  If fso.FolderExists(path) Then Exit Sub
  parent = fso.GetParentFolderName(path)
  If Len(parent) > 0 And Not fso.FolderExists(parent) Then EnsureFolder parent
  Err.Clear
  fso.CreateFolder path
  If Err.Number <> 0 Then
    WScript.Echo "[ERROR] Cannot create folder: " & path & " 0x" & Hex(Err.Number) & " " & Err.Description
    WScript.Quit 2
  End If
End Sub

Sub DeleteIfExists(ByVal path)
  Err.Clear
  If fso.FileExists(path) Then fso.DeleteFile path, True
  Err.Clear
End Sub

Sub RequireSuccess(ByVal stepName)
  Dim errNo, errText
  If Err.Number = 0 Then Exit Sub
  errNo = Err.Number
  errText = Err.Description
  Err.Clear
  FailCase stepName & ": " & errText, errNo, 10
End Sub

Sub RequireObject(ByVal value, ByVal stepName)
  If value Is Nothing Then FailCase stepName & ": CATIA returned Nothing", 9023, 10
End Sub

Sub FailCase(ByVal message, ByVal errNo, ByVal exitCode)
  On Error Resume Next
  WScript.Echo "[BLOCKED] " & fileName & " 0x" & Hex(errNo) & " " & message
  If Len(runtimeName) = 0 Then runtimeName = "unknown"
  WriteResult "blocked", "standalone repair failed 0x" & Hex(errNo) & " " & Clean(message)
  If Not doc Is Nothing Then doc.Close
  Set doc = Nothing
  DeleteIfExists tempPath
  Cleanup exitCode
  WScript.Quit exitCode
End Sub

Sub WriteResult(ByVal status, ByVal evidence)
  On Error Resume Next
  If Not ledger Is Nothing Then
    ledger.WriteLine fileName & vbTab & status & vbTab & runtimeName & vbTab & evidence
  End If
  If Not repairLedger Is Nothing Then
    repairLedger.WriteLine Stamp() & vbTab & fileName & vbTab & status & vbTab & runtimeName & vbTab & evidence
  End If
End Sub

Function Clean(ByVal value)
  Clean = Replace(Replace(CStr(value), vbTab, " "), vbCrLf, " ")
End Function

Sub Cleanup(ByVal exitCode)
  On Error Resume Next
  If Not doc Is Nothing Then doc.Close
  Set doc = Nothing
  If Not ledger Is Nothing Then ledger.Close
  Set ledger = Nothing
  If Not repairLedger Is Nothing Then repairLedger.Close
  Set repairLedger = Nothing
  If ownsCatia And Not catia Is Nothing Then catia.Quit
  Set catia = Nothing
End Sub
