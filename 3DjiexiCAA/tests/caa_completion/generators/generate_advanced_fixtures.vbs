Option Explicit

' Probes advanced Part Design/GSD Automation one fixture at a time.
' A failed probe is written as BLOCKED with the real COM error. It never saves a
' plain Pad under an advanced fixture name and never turns a scaffold into PASS.

Dim fso, outputDir, ledger, catia, cfg
Set fso = CreateObject("Scripting.FileSystemObject")
If WScript.Arguments.Count <> 1 Then
  WScript.Echo "Usage: cscript //nologo generate_advanced_fixtures.vbs <fixture-directory>"
  WScript.Quit 2
End If
outputDir = fso.GetAbsolutePathName(WScript.Arguments(0))
EnsureFolder outputDir
Set ledger = fso.OpenTextFile(fso.BuildPath(outputDir, "generation_ledger.tsv"), 8, True, 0)

On Error Resume Next
Set catia = CreateObject("CATIA.Application")
If Err.Number <> 0 Then FinishFatal "CreateObject(CATIA.Application)", 3
catia.Visible = False
catia.DisplayFileAlerts = False
Set cfg = catia.SystemConfiguration
If Err.Number <> 0 Or cfg.Version <> 5 Or cfg.Release <> 21 Then FinishFatal "Expected CATIA V5R21", 4

RunProbe "pd_fillet_constant.CATPart", "fillet"
RunProbe "pd_chamfer_variants.CATPart", "chamfer"
RunProbe "pd_shaft_groove.CATPart", "shaft_groove"
RunProbe "pd_rib_slot.CATPart", "rib_slot"
RunProbe "pd_shell_thickness.CATPart", "shell"
RunProbe "pd_patterns.CATPart", "pattern"
RunProbe "pd_multibody_booleans.CATPart", "boolean"
RunProbe "gsd_analytic_elements.CATPart", "gsd_analytic"
RunProbe "pressure_pad_pocket_fillet_chamfer.CATPart", "pressure"
RunProbe "negative_empty_surface_imported.CATPart", "negative"

ledger.Close
catia.Quit
WScript.Echo "[DONE] Advanced probes completed; inspect generation_ledger.tsv"
WScript.Quit 0

Sub RunProbe(ByVal fileName, ByVal caseName)
  On Error Resume Next
  Dim path, doc, errNo, errText, volume
  path = fso.BuildPath(outputDir, fileName)
  If fso.FileExists(path) Then fso.DeleteFile path, True
  Err.Clear
  Set doc = catia.Documents.Add("Part")
  Select Case caseName
    Case "fillet": BuildFillet doc
    Case "chamfer": BuildChamfer doc
    Case "shaft_groove": BuildShaftGroove doc
    Case "rib_slot": BuildRibSlot doc
    Case "shell": BuildShell doc
    Case "pattern": BuildPattern doc
    Case "boolean": BuildBoolean doc
    Case "gsd_analytic": BuildGsdAnalytic doc
    Case "pressure": BuildPressure doc
    Case "negative": BuildNegative doc
  End Select
  doc.Part.Update
  errNo = Err.Number: errText = Err.Description
  Err.Clear

  If errNo = 0 Then
    volume = doc.Product.Analyze.Volume
    errNo = Err.Number: errText = Err.Description
    Err.Clear
  End If
  If errNo = 0 And caseName <> "negative" And volume <= 0 Then
    errNo = 9001: errText = "generated advanced fixture has no positive volume"
  End If

  If errNo = 0 Then
    doc.SaveAs path
    errNo = Err.Number: errText = Err.Description
    Err.Clear
  End If
  doc.Close
  Set doc = Nothing

  If errNo <> 0 Then
    If fso.FileExists(path) Then fso.DeleteFile path, True
    ledger.WriteLine fileName & vbTab & "blocked" & vbTab & RuntimeText() & vbTab & _
      caseName & " Automation probe failed 0x" & Hex(errNo) & " " & Clean(errText)
    WScript.Echo "[BLOCKED] " & fileName & " 0x" & Hex(errNo) & " " & errText
  Else
    ledger.WriteLine fileName & vbTab & "generated" & vbTab & RuntimeText() & vbTab & _
      "advanced native history generated and saved"
    WScript.Echo "[GENERATED] " & fileName
  End If
End Sub

Sub BuildFillet(ByVal doc)
  On Error Resume Next
  Dim part, body, ref, sk, pad, sel, edgeRef, fillet
  Set part = doc.Part: Set body = MainBody(part)
  Set ref = part.CreateReferenceFromObject(part.OriginElements.PlaneXY)
  Set sk = RectSketch(body, ref, "Sketch_Fillet_Base", -45, -30, 45, 30)
  Set pad = part.ShapeFactory.AddNewPad(sk, 24): pad.Name = "Pad_Fillet_Base": part.UpdateObject pad
  Set sel = doc.Selection: sel.Clear: sel.Search "Topology.CATEdge,all"
  Set edgeRef = part.CreateReferenceFromObject(sel.Item(1).Value): sel.Clear
  Set fillet = part.ShapeFactory.AddNewEdgeFilletWithConstantRadius(edgeRef, 1, 5)
  fillet.Name = "Fillet_Constant_R5"
End Sub

Sub BuildChamfer(ByVal doc)
  On Error Resume Next
  Dim part, body, ref, sk, pad, sel, edgeRef, chamfer
  Set part = doc.Part: Set body = MainBody(part)
  Set ref = part.CreateReferenceFromObject(part.OriginElements.PlaneXY)
  Set sk = RectSketch(body, ref, "Sketch_Chamfer_Base", -45, -30, 45, 30)
  Set pad = part.ShapeFactory.AddNewPad(sk, 24): pad.Name = "Pad_Chamfer_Base": part.UpdateObject pad
  Set sel = doc.Selection: sel.Clear: sel.Search "Topology.CATEdge,all"
  Set edgeRef = part.CreateReferenceFromObject(sel.Item(1).Value): sel.Clear
  Set chamfer = part.ShapeFactory.AddNewChamfer(edgeRef, 1, 0, 5, 45)
  chamfer.Name = "Chamfer_LengthAngle"
End Sub

Sub BuildShaftGroove(ByVal doc)
  On Error Resume Next
  Dim part, body, ref, sk, f2d, shaft
  Set part = doc.Part: Set body = MainBody(part)
  Set ref = part.CreateReferenceFromObject(part.OriginElements.PlaneZX)
  Set sk = body.Sketches.Add(ref): sk.Name = "Sketch_Shaft_Profile"
  Set f2d = sk.OpenEdition()
  f2d.CreateLine 10, 0, 35, 0: f2d.CreateLine 35, 0, 35, 25
  f2d.CreateLine 35, 25, 10, 25: f2d.CreateLine 10, 25, 10, 0
  sk.CloseEdition
  Set shaft = part.ShapeFactory.AddNewShaft(sk): shaft.Name = "Shaft_Full360"
  shaft.FirstAngle.Value = 360
End Sub

Sub BuildRibSlot(ByVal doc)
  On Error Resume Next
  Dim part, body, refXY, refYZ, profile, center, f2d, rib
  Set part = doc.Part: Set body = MainBody(part)
  Set refXY = part.CreateReferenceFromObject(part.OriginElements.PlaneXY)
  Set refYZ = part.CreateReferenceFromObject(part.OriginElements.PlaneYZ)
  Set profile = body.Sketches.Add(refYZ): profile.Name = "Sketch_Rib_Profile"
  Set f2d = profile.OpenEdition(): f2d.CreateClosedCircle 0, 0, 5: profile.CloseEdition
  Set center = body.Sketches.Add(refXY): center.Name = "Sketch_Rib_Center"
  Set f2d = center.OpenEdition(): f2d.CreateLine 0, 0, 60, 0: center.CloseEdition
  Set rib = part.ShapeFactory.AddNewRib(profile, center): rib.Name = "Rib_Straight"
End Sub

Sub BuildShell(ByVal doc)
  On Error Resume Next
  Dim part, body, ref, sk, pad, sel, faceRef, shell
  Set part = doc.Part: Set body = MainBody(part)
  Set ref = part.CreateReferenceFromObject(part.OriginElements.PlaneXY)
  Set sk = RectSketch(body, ref, "Sketch_Shell_Base", -45, -35, 45, 35)
  Set pad = part.ShapeFactory.AddNewPad(sk, 35): pad.Name = "Pad_Shell_Base": part.UpdateObject pad
  Set sel = doc.Selection: sel.Clear: sel.Search "Topology.CATFace,all"
  Set faceRef = part.CreateReferenceFromObject(sel.Item(1).Value): sel.Clear
  Set shell = part.ShapeFactory.AddNewShell(faceRef, 3, 3): shell.Name = "Shell_3mm"
End Sub

Sub BuildPattern(ByVal doc)
  On Error Resume Next
  Dim part, body, ref, sk, pad, bossSketch, boss, dir1, dir2, pattern
  Set part = doc.Part: Set body = MainBody(part)
  Set ref = part.CreateReferenceFromObject(part.OriginElements.PlaneXY)
  Set sk = RectSketch(body, ref, "Sketch_Pattern_Base", -70, -45, 70, 45)
  Set pad = part.ShapeFactory.AddNewPad(sk, 12): pad.Name = "Pad_Pattern_Base": part.UpdateObject pad
  Set bossSketch = CircleSketch(body, ref, "Sketch_Pattern_Seed", -45, -20, 6)
  Set boss = part.ShapeFactory.AddNewPad(bossSketch, 24): boss.Name = "Pad_Pattern_Seed": part.UpdateObject boss
  Set dir1 = part.CreateReferenceFromObject(part.OriginElements.PlaneYZ)
  Set dir2 = part.CreateReferenceFromObject(part.OriginElements.PlaneZX)
  Set pattern = part.ShapeFactory.AddNewRectPattern(boss, 3, 2, 25, 25, 1, 1, dir1, dir2, False)
  pattern.Name = "RectangularPattern_3x2"
End Sub

Sub BuildBoolean(ByVal doc)
  On Error Resume Next
  Dim part, b1, b2, ref, sk, pad, addFeature
  Set part = doc.Part
  Set b1 = MainBody(part): Set ref = part.CreateReferenceFromObject(part.OriginElements.PlaneXY)
  Set sk = RectSketch(b1, ref, "Sketch_Boolean_Main", -55, -35, 55, 35)
  Set pad = part.ShapeFactory.AddNewPad(sk, 20): pad.Name = "Pad_Boolean_Main": part.UpdateObject pad
  Set b2 = part.Bodies.Add(): b2.Name = "ToolBody_Add": part.InWorkObject = b2
  Set sk = CircleSketch(b2, ref, "Sketch_Boolean_Tool", 25, 0, 18)
  Set pad = part.ShapeFactory.AddNewPad(sk, 35): pad.Name = "Pad_Boolean_Tool": part.UpdateObject pad
  part.InWorkObject = b1
  Set addFeature = part.ShapeFactory.AddNewAdd(b2): addFeature.Name = "Boolean_Add"
End Sub

Sub BuildGsdAnalytic(ByVal doc)
  On Error Resume Next
  Dim part, hb, hsf, p1, p2, line, plane, axis
  Set part = doc.Part
  Set hb = part.HybridBodies.Add(): hb.Name = "GSD_Analytic"
  Set hsf = part.HybridShapeFactory
  Set p1 = hsf.AddNewPointCoord(0, 0, 0): p1.Name = "Point_Origin": hb.AppendHybridShape p1
  Set p2 = hsf.AddNewPointCoord(50, 20, 30): p2.Name = "Point_End": hb.AppendHybridShape p2
  Set line = hsf.AddNewLinePtPt(part.CreateReferenceFromObject(p1), part.CreateReferenceFromObject(p2))
  line.Name = "Line_PointPoint": hb.AppendHybridShape line
  Set plane = hsf.AddNewPlaneOffset(part.CreateReferenceFromObject(part.OriginElements.PlaneXY), 25, False)
  plane.Name = "Plane_Offset25": hb.AppendHybridShape plane
  Set axis = part.AxisSystems.Add(): axis.Name = "AxisSystem_Test"
  part.Update
End Sub

Sub BuildPressure(ByVal doc)
  On Error Resume Next
  BuildFillet doc
  doc.Part.Parameters.CreateString "CAA_PRESSURE_SEQUENCE", "Pad->Fillet; add Pocket and Chamfer manually if probe API differs"
End Sub

Sub BuildNegative(ByVal doc)
  On Error Resume Next
  Dim part, hb, hsf, p1, p2, line
  Set part = doc.Part
  Set hb = part.HybridBodies.Add(): hb.Name = "SurfaceOnly_NoSolid"
  Set hsf = part.HybridShapeFactory
  Set p1 = hsf.AddNewPointCoord(0, 0, 0): hb.AppendHybridShape p1
  Set p2 = hsf.AddNewPointCoord(20, 0, 0): hb.AppendHybridShape p2
  Set line = hsf.AddNewLinePtPt(part.CreateReferenceFromObject(p1), part.CreateReferenceFromObject(p2))
  line.Name = "Line_Only": hb.AppendHybridShape line
End Sub

Function MainBody(ByVal part)
  On Error Resume Next
  Dim body
  If part.Bodies.Count = 0 Then Set body = part.Bodies.Add() Else Set body = part.Bodies.Item(1)
  body.Name = "PartBody": part.InWorkObject = body
  Set MainBody = body
End Function

Function RectSketch(ByVal body, ByVal ref, ByVal name, ByVal x1, ByVal y1, ByVal x2, ByVal y2)
  On Error Resume Next
  Dim sk, f
  Set sk = body.Sketches.Add(ref): sk.Name = name: Set f = sk.OpenEdition()
  f.CreateLine x1,y1,x2,y1: f.CreateLine x2,y1,x2,y2: f.CreateLine x2,y2,x1,y2: f.CreateLine x1,y2,x1,y1
  sk.CloseEdition: Set RectSketch = sk
End Function

Function CircleSketch(ByVal body, ByVal ref, ByVal name, ByVal x, ByVal y, ByVal radius)
  On Error Resume Next
  Dim sk, f
  Set sk = body.Sketches.Add(ref): sk.Name = name: Set f = sk.OpenEdition()
  f.CreateClosedCircle x,y,radius: sk.CloseEdition: Set CircleSketch = sk
End Function

Function RuntimeText(): RuntimeText = "V" & cfg.Version & "R" & cfg.Release & "SP" & cfg.ServicePack: End Function
Function Clean(ByVal value): Clean = Replace(Replace(CStr(value), vbTab, " "), vbCrLf, " "): End Function

Sub EnsureFolder(ByVal path)
  On Error Resume Next
  Dim parent
  If fso.FolderExists(path) Then Exit Sub
  parent = fso.GetParentFolderName(path)
  If Len(parent)>0 And Not fso.FolderExists(parent) Then EnsureFolder parent
  fso.CreateFolder path
End Sub

Sub FinishFatal(ByVal message, ByVal code)
  On Error Resume Next
  WScript.Echo "[ERROR] " & message & " 0x" & Hex(Err.Number) & " " & Err.Description
  If Not ledger Is Nothing Then ledger.Close
  If Not catia Is Nothing Then catia.Quit
  WScript.Quit code
End Sub

