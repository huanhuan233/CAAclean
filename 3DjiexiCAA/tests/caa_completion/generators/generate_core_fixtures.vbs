Option Explicit

' Deterministic CATIA V5R21 fixture generator for stable Automation APIs.
' It creates native CATPart history; no STEP import and no parser-output fabrication.

Const CAT_UP_TO_LAST_LIMIT = 2

Dim fso, outputDir, ledgerPath, ledger, catia, cfg, exitCode
Set fso = CreateObject("Scripting.FileSystemObject")
Set catia = Nothing
Set ledger = Nothing
exitCode = 1

If WScript.Arguments.Count <> 1 Then
  WScript.Echo "Usage: cscript //nologo generate_core_fixtures.vbs <fixture-directory>"
  WScript.Quit 2
End If

outputDir = fso.GetAbsolutePathName(WScript.Arguments(0))
EnsureFolder outputDir
ledgerPath = fso.BuildPath(outputDir, "generation_ledger.tsv")
Set ledger = fso.CreateTextFile(ledgerPath, True, False)
ledger.WriteLine "fixture" & vbTab & "status" & vbTab & "runtime" & vbTab & "evidence"

On Error Resume Next
Set catia = CreateObject("CATIA.Application")
RequireSuccess "CreateObject(CATIA.Application)", 3
catia.Visible = False
catia.DisplayFileAlerts = False
Set cfg = catia.SystemConfiguration
RequireSuccess "Read SystemConfiguration", 3
If cfg.Version <> 5 Or cfg.Release <> 21 Then Fail "Expected CATIA V5R21", 4

GeneratePart "pd_pad_primitives.CATPart", "pad_primitives"
GeneratePart "pd_pocket_depths.CATPart", "pocket_depths"
GeneratePart "geo_cavities.CATPart", "cavities"
GeneratePart "geo_slots_steps.CATPart", "slots_steps"
GeneratePart "measure_analytic_mass.CATPart", "measure"
GeneratePart "parameters_units_properties.CATPart", "parameters"
GeneratePart "business_fasteners.CATPart", "business_fasteners"
GeneratePart "business_seal_bond.CATPart", "business_seal_bond"
GeneratePart "registry_real_types.CATPart", "registry_real"
GeneratePart "registry_statuses.CATPart", "registry_status"
GenerateVersionParts

ledger.Close
Set ledger = Nothing
catia.Quit
Set catia = Nothing
WScript.Echo "[DONE] Core fixtures generated in " & outputDir
WScript.Quit 0

Sub GeneratePart(ByVal fileName, ByVal caseName)
  On Error Resume Next
  Dim path, doc, part, volume
  path = fso.BuildPath(outputDir, fileName)
  DeleteIfExists path
  Err.Clear
  Set doc = catia.Documents.Add("Part")
  RequireSuccess "Create Part for " & fileName, 10

  Select Case caseName
    Case "pad_primitives": BuildPadPrimitives doc
    Case "pocket_depths": BuildPocketDepths doc
    Case "cavities": BuildCavities doc
    Case "slots_steps": BuildSlotsSteps doc
    Case "measure": BuildMeasurePart doc
    Case "parameters": BuildParameterPart doc
    Case "business_fasteners": BuildBusinessFasteners doc
    Case "business_seal_bond": BuildBusinessSealBond doc
    Case "registry_real": BuildRegistryReal doc
    Case "registry_status": BuildRegistryStatuses doc
    Case Else: Fail "Unknown generator case: " & caseName, 11
  End Select

  Set part = doc.Part
  Err.Clear
  part.Update
  RequireSuccess "Part.Update " & fileName, 12
  volume = doc.Product.Analyze.Volume
  RequireSuccess "Measure volume " & fileName, 12
  If volume <= 0 Then Fail "Non-positive solid volume in " & fileName, 13

  Err.Clear
  doc.SaveAs path
  RequireSuccess "SaveAs " & fileName, 14
  doc.Close
  Set doc = Nothing

  VerifyReopen path
  ledger.WriteLine fileName & vbTab & "generated" & vbTab & RuntimeText() & vbTab & _
    "native CATPart; positive volume; reopen verified"
  WScript.Echo "[GENERATED] " & fileName
End Sub

Sub BuildPadPrimitives(ByVal doc)
  On Error Resume Next
  Dim part, body, planeRef, sf, sk, pad
  Set part = doc.Part
  Set body = EnsureMainBody(part)
  Set planeRef = part.CreateReferenceFromObject(part.OriginElements.PlaneXY)
  Set sf = part.ShapeFactory

  Set sk = AddRectangleSketch(body, planeRef, "Sketch_Pad_Rect", -60, -35, 60, 35)
  Set pad = sf.AddNewPad(sk, 12)
  pad.Name = "Pad_Rectangular"
  part.UpdateObject pad
  RequireSuccess "Pad_Rectangular", 20

  Set sk = AddCircleSketch(body, planeRef, "Sketch_Pad_Circle", 0, 0, 28)
  Set pad = sf.AddNewPad(sk, 20)
  pad.Name = "Pad_Circular"
  part.UpdateObject pad
  RequireSuccess "Pad_Circular", 20

  Set sk = AddPolygonSketch(body, planeRef, "Sketch_Pad_Irregular")
  Set pad = sf.AddNewPad(sk, 27)
  pad.Name = "Pad_Irregular"
  part.UpdateObject pad
  RequireSuccess "Pad_Irregular", 20

  Set sk = AddRectangleSketch(body, planeRef, "Sketch_Pad_Level4", -18, -12, 18, 12)
  Set pad = sf.AddNewPad(sk, 34)
  pad.Name = "Pad_MultiLevel_4"
  part.UpdateObject pad
  RequireSuccess "Pad_MultiLevel_4", 20
End Sub

Sub BuildPocketDepths(ByVal doc)
  On Error Resume Next
  Dim part, body, planeRef, sf, sk, feature
  Set part = doc.Part
  Set body = EnsureMainBody(part)
  Set planeRef = part.CreateReferenceFromObject(part.OriginElements.PlaneXY)
  Set sf = part.ShapeFactory

  Set sk = AddRectangleSketch(body, planeRef, "Sketch_Base", -75, -50, 75, 50)
  Set feature = sf.AddNewPad(sk, 25)
  feature.Name = "Pad_Base"
  part.UpdateObject feature

  Set sk = AddCircleSketch(body, planeRef, "Sketch_Pocket_Blind", -45, -20, 12)
  Set feature = sf.AddNewPocket(sk, 9)
  feature.Name = "Pocket_Blind"
  feature.DirectionOrientation = 0
  part.UpdateObject feature
  RequireSuccess "Pocket_Blind", 21

  Set sk = AddCircleSketch(body, planeRef, "Sketch_Pocket_Through", 0, -20, 10)
  Set feature = sf.AddNewPocket(sk, 25)
  feature.Name = "Pocket_Through"
  feature.DirectionOrientation = 0
  feature.FirstLimit.LimitMode = CAT_UP_TO_LAST_LIMIT
  part.UpdateObject feature
  RequireSuccess "Pocket_Through", 21

  Set sk = AddIslandSketch(body, planeRef, "Sketch_Pocket_Island", 38, 15)
  Set feature = sf.AddNewPocket(sk, 14)
  feature.Name = "Pocket_SingleIsland"
  feature.DirectionOrientation = 0
  part.UpdateObject feature
  RequireSuccess "Pocket_SingleIsland", 21

  Set sk = AddTwoCircleSketch(body, planeRef, "Sketch_Pocket_MultiContour", -35, 25, -5, 25)
  Set feature = sf.AddNewPocket(sk, 6)
  feature.Name = "Pocket_MultiContour"
  feature.DirectionOrientation = 0
  part.UpdateObject feature
  RequireSuccess "Pocket_MultiContour", 21
End Sub

Sub BuildCavities(ByVal doc)
  On Error Resume Next
  Dim part, body, planeRef, sf, sk, f
  Set part = doc.Part
  Set body = EnsureMainBody(part)
  Set planeRef = part.CreateReferenceFromObject(part.OriginElements.PlaneXY)
  Set sf = part.ShapeFactory
  Set sk = AddRectangleSketch(body, planeRef, "Sketch_Cavity_Block", -90, -65, 90, 65)
  Set f = sf.AddNewPad(sk, 30): f.Name = "Pad_Cavity_Block": part.UpdateObject f

  Set sk = AddRectangleSketch(body, planeRef, "Sketch_Cavity_Simple", -75, -50, -25, -5)
  Set f = sf.AddNewPocket(sk, 12): f.Name = "Pocket_Cavity_Simple": f.DirectionOrientation = 0: part.UpdateObject f

  Set sk = AddRectangleSketch(body, planeRef, "Sketch_Cavity_Level2", -65, -40, -35, -15)
  Set f = sf.AddNewPocket(sk, 20): f.Name = "Pocket_Cavity_Level2": f.DirectionOrientation = 0: part.UpdateObject f

  Set sk = AddIslandSketch(body, planeRef, "Sketch_Cavity_Island", 35, -20)
  Set f = sf.AddNewPocket(sk, 16): f.Name = "Pocket_Cavity_SingleIsland": f.DirectionOrientation = 0: part.UpdateObject f

  Set sk = AddNestedIslandSketch(body, planeRef, "Sketch_Cavity_NestedIsland", 35, 35)
  Set f = sf.AddNewPocket(sk, 10): f.Name = "Pocket_Cavity_NestedIsland": f.DirectionOrientation = 0: part.UpdateObject f
  RequireSuccess "Cavity history", 22
End Sub

Sub BuildSlotsSteps(ByVal doc)
  On Error Resume Next
  Dim part, body, planeRef, sf, sk, f
  Set part = doc.Part
  Set body = EnsureMainBody(part)
  Set planeRef = part.CreateReferenceFromObject(part.OriginElements.PlaneXY)
  Set sf = part.ShapeFactory
  Set sk = AddRectangleSketch(body, planeRef, "Sketch_Slot_Base", -100, -70, 100, 70)
  Set f = sf.AddNewPad(sk, 18): f.Name = "Pad_Slot_Base": part.UpdateObject f

  Set sk = AddRectangleSketch(body, planeRef, "Sketch_OpenSlot", -100, -50, -65, -25)
  Set f = sf.AddNewPocket(sk, 18): f.Name = "Pocket_OpenSlot": f.DirectionOrientation = 0: part.UpdateObject f
  Set sk = AddRectangleSketch(body, planeRef, "Sketch_ClosedSlot", -45, -50, -10, -25)
  Set f = sf.AddNewPocket(sk, 10): f.Name = "Pocket_ClosedSlot": f.DirectionOrientation = 0: part.UpdateObject f
  Set sk = AddRoundEndSlotSketch(body, planeRef, "Sketch_RoundEndSlot", 25, -37, 18, 8)
  Set f = sf.AddNewPocket(sk, 12): f.Name = "Pocket_RoundEndSlot": f.DirectionOrientation = 0: part.UpdateObject f
  Set sk = AddDovetailSketch(body, planeRef, "Sketch_Dovetail", 65, -50)
  Set f = sf.AddNewPocket(sk, 8): f.Name = "Pocket_Dovetail": f.DirectionOrientation = 0: part.UpdateObject f

  Set sk = AddRectangleSketch(body, planeRef, "Sketch_Step_1", -80, 15, -20, 60)
  Set f = sf.AddNewPad(sk, 28): f.Name = "Pad_OuterStep_1": part.UpdateObject f
  Set sk = AddRectangleSketch(body, planeRef, "Sketch_Step_2", -60, 25, -35, 50)
  Set f = sf.AddNewPad(sk, 38): f.Name = "Pad_OuterStep_2": part.UpdateObject f
  Set sk = AddCircleSketch(body, planeRef, "Sketch_Shoulder", 50, 35, 25)
  Set f = sf.AddNewPad(sk, 32): f.Name = "Pad_ShaftShoulder": part.UpdateObject f
  RequireSuccess "Slots and steps history", 23
End Sub

Sub BuildMeasurePart(ByVal doc)
  On Error Resume Next
  Dim part, body, planeRef, sf, sk, f, params
  Set part = doc.Part
  Set body = EnsureMainBody(part)
  Set planeRef = part.CreateReferenceFromObject(part.OriginElements.PlaneXY)
  Set sf = part.ShapeFactory
  Set sk = AddRectangleSketch(body, planeRef, "Sketch_Measure", -40, -30, 40, 30)
  Set f = sf.AddNewPad(sk, 20): f.Name = "Pad_MeasureBlock": part.UpdateObject f
  Set sk = AddCircleSketch(body, planeRef, "Sketch_MeasureCylinder", 0, 0, 15)
  Set f = sf.AddNewPad(sk, 35): f.Name = "Pad_MeasureCylinder": part.UpdateObject f
  Set params = part.Parameters
  params.CreateString "CAA_MaterialHint", "steel-test"
  params.CreateReal "CAA_DensityHint", 7850
  params.CreateString "CAA_MeasureExpected", "volume;area;mass;cog;inertia;bbox"
  RequireSuccess "Measurement parameters", 24
End Sub

Sub BuildParameterPart(ByVal doc)
  On Error Resume Next
  Dim part, body, planeRef, sf, sk, f, params
  Set part = doc.Part
  Set body = EnsureMainBody(part)
  Set planeRef = part.CreateReferenceFromObject(part.OriginElements.PlaneXY)
  Set sf = part.ShapeFactory
  Set sk = AddRectangleSketch(body, planeRef, "Sketch_Parameters", -30, -20, 30, 20)
  Set f = sf.AddNewPad(sk, 16): f.Name = "Pad_ParameterCarrier": part.UpdateObject f
  Set params = part.Parameters
  params.CreateString "CAA_String", "alpha"
  params.CreateString "CAA_EmptyString", ""
  params.CreateReal "CAA_Real", 3.1415926
  params.CreateInteger "CAA_Integer", 42
  params.CreateBoolean "CAA_Boolean", True
  params.CreateDimension "CAA_Length", "LENGTH", 0.025
  params.CreateDimension "CAA_Angle", "ANGLE", 0.523598775598299
  params.CreateString "CAA_UnknownUnitNegative", "17 quux"
  params.CreateString "CAA_CustomProperty", "fixture-value"
  RequireSuccess "Typed parameters", 25
End Sub

Sub BuildBusinessFasteners(ByVal doc)
  On Error Resume Next
  Dim part
  BuildSimpleCarrier doc, "Pad_BusinessFastenerCarrier"
  Set part = doc.Part
  AddNamedGeometricalSet part, U_Boss() & ".1", Array("" & U_FeatureType(), U_Boss(), "Diameter", "12 mm")
  AddNamedGeometricalSet part, U_Hole() & ".1", Array("" & U_FeatureType(), U_Hole(), "Diameter", "10 mm")
  AddNamedGeometricalSet part, U_Slot() & ".1", Array("" & U_FeatureType(), U_Slot(), "Width", "8 mm")
  AddNamedGeometricalSet part, U_Hole() & ".2", Array("Alias", "FASTENER_PATH_B", "PointCount", "3")
  AddNamedGeometricalSet part, "Fastener_MissingAlias", Array("Status", "negative")
  RequireSuccess "Business fastener sets", 26
End Sub

Sub BuildBusinessSealBond(ByVal doc)
  On Error Resume Next
  Dim part
  BuildSimpleCarrier doc, "Pad_BusinessSealBondCarrier"
  Set part = doc.Part
  AddNamedGeometricalSet part, U_Seal() & ".1", Array("DefinitionType", "seal", "Group", "A")
  AddNamedGeometricalSet part, U_Seal() & ".2", Array("DefinitionType", "seal", "Parent", "A")
  AddNamedGeometricalSet part, U_Bond() & ".1", Array("DefinitionType", "bond", "Group", "B")
  AddNamedGeometricalSet part, U_Bond() & ".2", Array("DefinitionType", "bond", "Parent", "B")
  AddNamedGeometricalSet part, "Business_MissingFields", Array("Status", "negative")
  RequireSuccess "Business seal/bond sets", 27
End Sub

Sub BuildRegistryReal(ByVal doc)
  On Error Resume Next
  BuildPocketDepths doc
  doc.Part.Parameters.CreateString "CAA_RegistryCase", "typed;generic;opaque;supertype"
  RequireSuccess "Registry real fixture", 28
End Sub

Sub BuildRegistryStatuses(ByVal doc)
  On Error Resume Next
  BuildSimpleCarrier doc, "Pad_Verified"
  Dim part
  Set part = doc.Part
  part.Parameters.CreateString "CAA_EXPECTED_STATUS_1", "verified"
  part.Parameters.CreateString "CAA_EXPECTED_STATUS_2", "needs_review"
  part.Parameters.CreateString "CAA_EXPECTED_STATUS_3", "unsupported"
  part.Parameters.CreateString "CAA_EXPECTED_STATUS_4", "failed"
  part.Parameters.CreateString "CAA_EXPECTED_STATUS_5", "stale"
  RequireSuccess "Registry status parameters", 29
End Sub

Sub GenerateVersionParts()
  On Error Resume Next
  Dim v1, v2, doc, part, pad
  v1 = fso.BuildPath(outputDir, "version_part_v1.CATPart")
  v2 = fso.BuildPath(outputDir, "version_part_v2.CATPart")
  DeleteIfExists v1: DeleteIfExists v2
  Set doc = catia.Documents.Add("Part")
  BuildPocketDepths doc
  doc.Part.Update
  doc.SaveAs v1
  RequireSuccess "Save version_part_v1", 30
  doc.Close

  Set doc = catia.Documents.Open(v1)
  Set part = doc.Part
  Set pad = part.FindObjectByName("Pad_Base")
  pad.FirstLimit.Dimension.Value = 31
  part.Parameters.CreateString "CAA_VERSION_CHANGE", "pad_length_and_parameter_changed"
  part.Update
  doc.SaveAs v2
  RequireSuccess "Save version_part_v2", 30
  doc.Close
  VerifyReopen v1: VerifyReopen v2
  ledger.WriteLine "version_part_v1.CATPart|version_part_v2.CATPart" & vbTab & "generated" & vbTab & RuntimeText() & vbTab & "real CATIA derived pair"

  GenerateBusinessVersionPair
End Sub

Sub GenerateBusinessVersionPair()
  On Error Resume Next
  Dim v1, v2, doc, part
  v1 = fso.BuildPath(outputDir, "version_business_v1.CATPart")
  v2 = fso.BuildPath(outputDir, "version_business_v2.CATPart")
  DeleteIfExists v1: DeleteIfExists v2
  Set doc = catia.Documents.Add("Part")
  BuildBusinessSealBond doc
  doc.Part.Update
  doc.SaveAs v1
  doc.Close
  Set doc = catia.Documents.Open(v1)
  Set part = doc.Part
  AddNamedGeometricalSet part, U_Bond() & ".3", Array("DefinitionType", "bond", "Change", "added-in-v2")
  part.Update
  doc.SaveAs v2
  RequireSuccess "Save business version pair", 31
  doc.Close
  VerifyReopen v1: VerifyReopen v2
  ledger.WriteLine "version_business_v1.CATPart|version_business_v2.CATPart" & vbTab & "generated" & vbTab & RuntimeText() & vbTab & "real business-definition pair"
End Sub

Sub BuildSimpleCarrier(ByVal doc, ByVal padName)
  On Error Resume Next
  Dim part, body, planeRef, sk, pad
  Set part = doc.Part
  Set body = EnsureMainBody(part)
  Set planeRef = part.CreateReferenceFromObject(part.OriginElements.PlaneXY)
  Set sk = AddRectangleSketch(body, planeRef, "Sketch_Carrier", -50, -35, 50, 35)
  Set pad = part.ShapeFactory.AddNewPad(sk, 15)
  pad.Name = padName
  part.UpdateObject pad
  RequireSuccess "BuildSimpleCarrier", 32
End Sub

Function EnsureMainBody(ByVal part)
  On Error Resume Next
  Dim body
  If part.Bodies.Count = 0 Then
    Set body = part.Bodies.Add()
  Else
    Set body = part.Bodies.Item(1)
  End If
  body.Name = "PartBody"
  part.InWorkObject = body
  Set EnsureMainBody = body
End Function

Function AddRectangleSketch(ByVal body, ByVal planeRef, ByVal name, ByVal x1, ByVal y1, ByVal x2, ByVal y2)
  On Error Resume Next
  Dim sk, f2d
  Set sk = body.Sketches.Add(planeRef)
  sk.Name = name
  Set f2d = sk.OpenEdition()
  f2d.CreateLine x1, y1, x2, y1
  f2d.CreateLine x2, y1, x2, y2
  f2d.CreateLine x2, y2, x1, y2
  f2d.CreateLine x1, y2, x1, y1
  sk.CloseEdition
  Set AddRectangleSketch = sk
End Function

Function AddCircleSketch(ByVal body, ByVal planeRef, ByVal name, ByVal x, ByVal y, ByVal radius)
  On Error Resume Next
  Dim sk, f2d
  Set sk = body.Sketches.Add(planeRef): sk.Name = name
  Set f2d = sk.OpenEdition(): f2d.CreateClosedCircle x, y, radius: sk.CloseEdition
  Set AddCircleSketch = sk
End Function

Function AddPolygonSketch(ByVal body, ByVal planeRef, ByVal name)
  On Error Resume Next
  Dim sk, f2d
  Set sk = body.Sketches.Add(planeRef): sk.Name = name
  Set f2d = sk.OpenEdition()
  f2d.CreateLine -42, -24, 34, -30
  f2d.CreateLine 34, -30, 48, 4
  f2d.CreateLine 48, 4, 18, 27
  f2d.CreateLine 18, 27, -38, 20
  f2d.CreateLine -38, 20, -42, -24
  sk.CloseEdition
  Set AddPolygonSketch = sk
End Function

Function AddIslandSketch(ByVal body, ByVal planeRef, ByVal name, ByVal cx, ByVal cy)
  On Error Resume Next
  Dim sk, f2d
  Set sk = body.Sketches.Add(planeRef): sk.Name = name
  Set f2d = sk.OpenEdition()
  f2d.CreateClosedCircle cx, cy, 22
  f2d.CreateClosedCircle cx, cy, 8
  sk.CloseEdition
  Set AddIslandSketch = sk
End Function

Function AddNestedIslandSketch(ByVal body, ByVal planeRef, ByVal name, ByVal cx, ByVal cy)
  On Error Resume Next
  Dim sk, f2d
  Set sk = body.Sketches.Add(planeRef): sk.Name = name
  Set f2d = sk.OpenEdition()
  f2d.CreateClosedCircle cx, cy, 24
  f2d.CreateClosedCircle cx, cy, 14
  f2d.CreateClosedCircle cx, cy, 5
  sk.CloseEdition
  Set AddNestedIslandSketch = sk
End Function

Function AddTwoCircleSketch(ByVal body, ByVal planeRef, ByVal name, ByVal x1, ByVal y1, ByVal x2, ByVal y2)
  On Error Resume Next
  Dim sk, f2d
  Set sk = body.Sketches.Add(planeRef): sk.Name = name
  Set f2d = sk.OpenEdition()
  f2d.CreateClosedCircle x1, y1, 8
  f2d.CreateClosedCircle x2, y2, 8
  sk.CloseEdition
  Set AddTwoCircleSketch = sk
End Function

Function AddRoundEndSlotSketch(ByVal body, ByVal planeRef, ByVal name, ByVal cx, ByVal cy, ByVal halfLength, ByVal radius)
  On Error Resume Next
  Dim sk, f2d
  Set sk = body.Sketches.Add(planeRef): sk.Name = name
  Set f2d = sk.OpenEdition()
  f2d.CreateLine cx-halfLength, cy-radius, cx+halfLength, cy-radius
  f2d.CreateLine cx+halfLength, cy+radius, cx-halfLength, cy+radius
  f2d.CreateCircle cx-halfLength, cy, radius, 1.5707963267949, 4.71238898038469
  f2d.CreateCircle cx+halfLength, cy, radius, -1.5707963267949, 1.5707963267949
  sk.CloseEdition
  Set AddRoundEndSlotSketch = sk
End Function

Function AddDovetailSketch(ByVal body, ByVal planeRef, ByVal name, ByVal cx, ByVal cy)
  On Error Resume Next
  Dim sk, f2d
  Set sk = body.Sketches.Add(planeRef): sk.Name = name
  Set f2d = sk.OpenEdition()
  f2d.CreateLine cx-16, cy, cx+16, cy
  f2d.CreateLine cx+16, cy, cx+10, cy+20
  f2d.CreateLine cx+10, cy+20, cx-10, cy+20
  f2d.CreateLine cx-10, cy+20, cx-16, cy
  sk.CloseEdition
  Set AddDovetailSketch = sk
End Function

Sub AddNamedGeometricalSet(ByVal part, ByVal setName, ByVal keyValues)
  On Error Resume Next
  Dim hb, hsf, point, i, parameterName
  Set hb = part.HybridBodies.Add()
  hb.Name = setName
  Set hsf = part.HybridShapeFactory
  Set point = hsf.AddNewPointCoord(part.HybridBodies.Count * 5, 0, 0)
  point.Name = "EvidencePoint"
  hb.AppendHybridShape point
  For i = 0 To UBound(keyValues) Step 2
    parameterName = Replace(setName, ".", "_") & "_" & CStr(keyValues(i))
    part.Parameters.CreateString parameterName, CStr(keyValues(i + 1))
  Next
  part.Update
End Sub

Sub VerifyReopen(ByVal path)
  On Error Resume Next
  Dim doc, volume
  Set doc = catia.Documents.Open(path)
  RequireSuccess "Reopen " & fso.GetFileName(path), 40
  volume = doc.Product.Analyze.Volume
  RequireSuccess "Reopened volume " & fso.GetFileName(path), 40
  If volume <= 0 Then Fail "Reopened fixture has no positive volume: " & path, 41
  doc.Close
End Sub

Function RuntimeText()
  RuntimeText = "V" & CStr(cfg.Version) & "R" & CStr(cfg.Release) & "SP" & CStr(cfg.ServicePack)
End Function

Function U_Boss(): U_Boss = ChrW(&H51F8) & ChrW(&H53F0): End Function
Function U_Hole(): U_Hole = ChrW(&H5B54): End Function
Function U_Slot(): U_Slot = ChrW(&H69FD): End Function
Function U_FeatureType(): U_FeatureType = ChrW(&H7279) & ChrW(&H5F81) & ChrW(&H7C7B) & ChrW(&H578B): End Function
Function U_Seal(): U_Seal = "K_" & ChrW(&H5BC6) & ChrW(&H5C01) & ChrW(&H5B9A) & ChrW(&H4E49): End Function
Function U_Bond(): U_Bond = "M_" & ChrW(&H80F6) & ChrW(&H63A5) & ChrW(&H5B9A) & ChrW(&H4E49): End Function

Sub DeleteIfExists(ByVal path)
  On Error Resume Next
  If fso.FileExists(path) Then fso.DeleteFile path, True
  RequireSuccess "Delete previous " & path, 50
End Sub

Sub EnsureFolder(ByVal path)
  On Error Resume Next
  Dim parent
  If fso.FolderExists(path) Then Exit Sub
  parent = fso.GetParentFolderName(path)
  If Len(parent) > 0 And Not fso.FolderExists(parent) Then EnsureFolder parent
  fso.CreateFolder path
End Sub

Sub RequireSuccess(ByVal stage, ByVal code)
  On Error Resume Next
  If Err.Number <> 0 Then
    Dim n, d
    n = "0x" & Hex(Err.Number): d = Err.Description: Err.Clear
    Fail stage & " failed: " & n & " " & d, code
  End If
End Sub

Sub Fail(ByVal message, ByVal code)
  On Error Resume Next
  WScript.Echo "[ERROR] " & message
  If Not ledger Is Nothing Then ledger.WriteLine "generator" & vbTab & "failed" & vbTab & RuntimeText() & vbTab & Replace(message, vbTab, " ")
  If Not ledger Is Nothing Then ledger.Close
  If Not catia Is Nothing Then catia.Quit
  WScript.Quit code
End Sub

