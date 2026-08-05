Option Explicit

' Builds real CATPart carriers and attempts a minimal FTA text through public Automation.
' Full GD&T construction remains in the manual checklist when R21 license/API blocks automation.
' A carrier without a verified AnnotationSet is saved with *_scaffold.CATPart, never with the
' final fixture filename.

Dim fso, fixtureDir, ledger, catia, cfg
Set fso = CreateObject("Scripting.FileSystemObject")
If WScript.Arguments.Count <> 1 Then
  WScript.Echo "Usage: cscript //nologo prepare_fta_scaffolds.vbs <fixture-directory>"
  WScript.Quit 2
End If
fixtureDir = fso.GetAbsolutePathName(WScript.Arguments(0))
Set ledger = fso.OpenTextFile(fso.BuildPath(fixtureDir, "generation_ledger.tsv"), 8, True, 0)

On Error Resume Next
Set catia = CreateObject("CATIA.Application")
If Err.Number <> 0 Then Fatal "Create CATIA.Application", 3
catia.Visible = False: catia.DisplayFileAlerts = False
Set cfg = catia.SystemConfiguration
If Err.Number <> 0 Or cfg.Version <> 5 Or cfg.Release <> 21 Then Fatal "Expected CATIA V5R21", 4

BuildFtaCarrier "fta_all_semantic_types"
BuildFtaCarrier "fta_geometry_references"
BuildFtaCarrier "fta_orphan_invalid"
BuildFtaCarrier "version_fta_v1"

ledger.Close: catia.Quit
WScript.Echo "[DONE] FTA probes/scaffolds completed"
WScript.Quit 0

Sub BuildFtaCarrier(ByVal baseName)
  On Error Resume Next
  Dim finalPath, scaffoldPath, doc, part, body, ref, sk, f2d, pad, sel, faceRef
  Dim annSets, annSet, userSurfaces, userSurface, annFactory, ann, e, d
  finalPath = fso.BuildPath(fixtureDir, baseName & ".CATPart")
  scaffoldPath = fso.BuildPath(fixtureDir, baseName & "_scaffold.CATPart")
  If fso.FileExists(finalPath) Then fso.DeleteFile finalPath, True
  If fso.FileExists(scaffoldPath) Then fso.DeleteFile scaffoldPath, True
  Err.Clear
  Set doc = catia.Documents.Add("Part")
  Set part = doc.Part
  If part.Bodies.Count = 0 Then Set body = part.Bodies.Add() Else Set body = part.Bodies.Item(1)
  body.Name = "PartBody": part.InWorkObject = body
  Set ref = part.CreateReferenceFromObject(part.OriginElements.PlaneXY)
  Set sk = body.Sketches.Add(ref): sk.Name = "Sketch_FTA_Carrier"
  Set f2d = sk.OpenEdition()
  f2d.CreateLine -60,-40,60,-40: f2d.CreateLine 60,-40,60,40
  f2d.CreateLine 60,40,-60,40: f2d.CreateLine -60,40,-60,-40
  sk.CloseEdition
  Set pad = part.ShapeFactory.AddNewPad(sk, 25): pad.Name = "Pad_FTA_Carrier": part.UpdateObject pad
  part.Parameters.CreateString "CAA_FTA_FIXTURE", baseName
  part.Parameters.CreateString "CAA_EXPECTED_FTA_TYPES", "dimension;limit-deviation;gdt;datum;roughness;text;flag;noa;view;capture"

  Set sel = doc.Selection: sel.Clear: sel.Search "Topology.CATFace,all"
  Set faceRef = part.CreateReferenceFromObject(sel.Item(1).Value): sel.Clear
  Set annSets = part.AnnotationSets
  Set annSet = annSets.Add("ISO_3D")
  annSet.SwitchOn = True
  Set userSurfaces = part.UserSurfaces
  Set userSurface = userSurfaces.Generate(faceRef)
  Set annFactory = annSet.AnnotationFactory
  Set ann = annFactory.CreateEvoluateText(userSurface, 20, 20, 35, True)
  ann.Name = "CAA_Text_FaceReference"
  ann.Text.Text = "CAA V5R21 FTA extraction fixture"
  ann.ModifyVisu
  part.Update
  If annSets.Count < 1 Or annSet.Annotations.Count < 1 Then Err.Raise 9201, , "FTA objects were not persisted"
  e = Err.Number: d = Err.Description: Err.Clear

  If e = 0 Then
    doc.SaveAs finalPath
    e = Err.Number: d = Err.Description: Err.Clear
  Else
    doc.SaveAs scaffoldPath
    Err.Clear
  End If
  doc.Close

  If e = 0 Then
    ledger.WriteLine baseName & ".CATPart" & vbTab & "generated" & vbTab & RuntimeText() & vbTab & "real AnnotationSet + UserSurface + text; remaining semantic types require checklist"
    WScript.Echo "[GENERATED] " & baseName & ".CATPart (minimal real FTA present)"
  Else
    ledger.WriteLine baseName & ".CATPart" & vbTab & "blocked" & vbTab & RuntimeText() & vbTab & "FTA Automation/license 0x" & Hex(e) & " " & Clean(d) & "; carrier saved as scaffold only"
    WScript.Echo "[BLOCKED] " & baseName & ".CATPart; scaffold saved; 0x" & Hex(e) & " " & d
  End If
End Sub

Function RuntimeText(): RuntimeText = "V" & cfg.Version & "R" & cfg.Release & "SP" & cfg.ServicePack: End Function
Function Clean(ByVal v): Clean = Replace(Replace(CStr(v), vbTab, " "), vbCrLf, " "): End Function
Sub Fatal(ByVal message, ByVal code)
  On Error Resume Next
  WScript.Echo "[ERROR] " & message & " 0x" & Hex(Err.Number) & " " & Err.Description
  ledger.Close: If Not catia Is Nothing Then catia.Quit
  WScript.Quit code
End Sub

