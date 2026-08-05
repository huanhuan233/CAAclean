Option Explicit

' Builds real CATPart geometry carriers for FTA/MBD manual completion.
' The script does not mark final FTA semantic fixtures as generated unless native semantic
' annotations are actually present. R21 Automation probing remains conservative by design.

Dim fso, fixtureDir, ledger, catia, cfg, backupDir
Set fso = CreateObject("Scripting.FileSystemObject")
If WScript.Arguments.Count = 1 And LCase(WScript.Arguments(0)) = "--syntax-check" Then
  WScript.Echo "[SYNTAX-OK] prepare_fta_scaffolds.vbs"
  WScript.Quit 0
End If
If WScript.Arguments.Count <> 1 Then
  WScript.Echo "Usage: cscript //nologo prepare_fta_scaffolds.vbs <fixture-directory>"
  WScript.Quit 2
End If

fixtureDir = fso.GetAbsolutePathName(WScript.Arguments(0))
backupDir = fso.BuildPath(fixtureDir, "product_fta_backups")
If Not fso.FolderExists(fixtureDir) Then fso.CreateFolder fixtureDir
If Not fso.FolderExists(backupDir) Then fso.CreateFolder backupDir
Set ledger = fso.OpenTextFile(fso.BuildPath(fixtureDir, "generation_ledger.tsv"), 8, True, 0)

Set catia = CreateCatia()
catia.Visible = False
catia.DisplayFileAlerts = False
Set cfg = catia.SystemConfiguration
If cfg.Version <> 5 Or cfg.Release <> 21 Then Fatal "Expected CATIA V5R21, got " & RuntimeText(), 4
WScript.Echo "[CATIA] " & RuntimeText()

BuildFtaCarrier "fta_all_semantic_types"
BuildFtaCarrier "fta_geometry_references"
BuildFtaCarrier "fta_orphan_invalid"
BuildFtaCarrier "version_fta_v1"

ledger.Close
catia.Quit
WScript.Echo "[DONE] FTA geometry scaffolds completed; native semantic FTA still requires manual checklist"
WScript.Quit 0

Sub BuildFtaCarrier(ByVal baseName)
  Dim scaffoldPath, tmpPath, doc, part, body, planeRef, sk, f2d, pad, skHole, pocket, axisSystems, axisSystem, ok
  scaffoldPath = fso.BuildPath(fixtureDir, baseName & "_scaffold.CATPart")
  tmpPath = TempPath(baseName & "_scaffold.CATPart")

  Set doc = catia.Documents.Add("Part")
  Set part = doc.Part
  If part.Bodies.Count = 0 Then Set body = part.Bodies.Add() Else Set body = part.Bodies.Item(1)
  body.Name = "PartBody"
  part.InWorkObject = body

  Set planeRef = part.CreateReferenceFromObject(part.OriginElements.PlaneXY)
  Set sk = body.Sketches.Add(planeRef)
  sk.Name = "Sketch_FTA_Block_Profile"
  Set f2d = sk.OpenEdition()
  f2d.CreateLine -60, -40, 60, -40
  f2d.CreateLine 60, -40, 60, 40
  f2d.CreateLine 60, 40, -60, 40
  f2d.CreateLine -60, 40, -60, -40
  sk.CloseEdition
  Set pad = part.ShapeFactory.AddNewPad(sk, 25)
  pad.Name = "Pad_FTA_Carrier"
  part.UpdateObject pad

  Set skHole = body.Sketches.Add(part.CreateReferenceFromBRepName("Face:(Brp:(Pad_FTA_Carrier;2);None:();Cf11:());WithTemporaryBody;WithoutBuildError;WithSelectingFeatureSupport;MFBRepVersion_CXR15)", pad))
  skHole.Name = "Sketch_FTA_Hole_Profile"
  Set f2d = skHole.OpenEdition()
  f2d.CreateClosedCircle 0, 0, 12
  skHole.CloseEdition
  Set pocket = part.ShapeFactory.AddNewPocket(skHole, 30)
  pocket.Name = "Pocket_FTA_TargetHole"
  part.UpdateObject pocket

  Set axisSystems = part.AxisSystems
  Set axisSystem = axisSystems.Add()
  axisSystem.Name = "AxisSystem_FTA_Datum"
  part.Parameters.CreateString "CAA_FTA_FIXTURE", baseName
  part.Parameters.CreateString "CAA_MANUAL_TARGET_FACE", "Pad_FTA_Carrier top planar face"
  part.Parameters.CreateString "CAA_MANUAL_TARGET_EDGE", "Pad_FTA_Carrier vertical outside edge"
  part.Parameters.CreateString "CAA_MANUAL_TARGET_HOLE", "Pocket_FTA_TargetHole cylindrical face / hole axis"
  part.Parameters.CreateString "CAA_EXPECTED_FTA_TYPES", ManualTypes()
  part.Update
  SaveClose doc, tmpPath

  ok = VerifyCarrierFile(tmpPath, baseName)
  If ok Then
    BackupExisting scaffoldPath
    If fso.FileExists(scaffoldPath) Then fso.DeleteFile scaffoldPath, True
    fso.MoveFile tmpPath, scaffoldPath
    ledger.WriteLine fso.GetFileName(scaffoldPath) & vbTab & "generated" & vbTab & RuntimeText() & vbTab & "real geometry carrier: pad, hole pocket, datum axis system"
    ledger.WriteLine baseName & ".CATPart" & vbTab & "blocked" & vbTab & RuntimeText() & vbTab & "native FTA semantics require manual CATIA FTA/MBD operations; scaffold=" & fso.GetFileName(scaffoldPath)
    WScript.Echo "[SCAFFOLD] " & fso.GetFileName(scaffoldPath)
    WScript.Echo "[FTA-MANUAL] " & baseName & ".CATPart requires native Annotation Set/TPS objects; not promoted as final"
  Else
    ledger.WriteLine baseName & ".CATPart" & vbTab & "blocked" & vbTab & RuntimeText() & vbTab & "geometry scaffold close/reopen verification failed; temporary retained=" & fso.GetFileName(tmpPath)
    WScript.Echo "[BLOCKED] " & baseName & " scaffold verification failed; temporary retained " & tmpPath
  End If
End Sub

Function VerifyCarrierFile(ByVal path, ByVal label)
  Dim doc, part, shapes, volume
  VerifyCarrierFile = False
  Err.Clear
  On Error Resume Next
  Set doc = catia.Documents.Open(path)
  Dim e, d: e = Err.Number: d = Err.Description
  On Error GoTo 0
  If e <> 0 Then
    WScript.Echo "[VERIFY-ERROR] " & label & " open 0x" & Hex(e) & " " & d
    Exit Function
  End If
  Set part = doc.Part
  shapes = part.Bodies.Item(1).Shapes.Count
  Err.Clear
  On Error Resume Next
  volume = doc.Product.Analyze.Volume
  e = Err.Number
  On Error GoTo 0
  doc.Close
  If shapes < 2 Or e <> 0 Or CDbl(volume) <= 0 Then
    WScript.Echo "[VERIFY-ERROR] " & label & " shapes=" & shapes & " volume=" & volume
    Exit Function
  End If
  WScript.Echo "[REOPEN-OK] " & fso.GetFileName(path) & " shapes=" & shapes & " volume=" & volume
  VerifyCarrierFile = True
End Function

Sub SaveClose(ByVal doc, ByVal path)
  If fso.FileExists(path) Then fso.DeleteFile path, True
  Err.Clear
  On Error Resume Next
  doc.SaveAs path
  Dim e, d: e = Err.Number: d = Err.Description
  On Error GoTo 0
  If e <> 0 Then Fatal "SaveAs " & path & " 0x" & Hex(e) & " " & d, 20
  doc.Close
End Sub

Sub BackupExisting(ByVal path)
  If Not fso.FileExists(path) Then Exit Sub
  Dim stamped
  stamped = fso.BuildPath(backupDir, fso.GetBaseName(path) & "_" & Timestamp() & "." & fso.GetExtensionName(path))
  fso.CopyFile path, stamped, True
  WScript.Echo "[BACKUP] " & path & " -> " & stamped
End Sub

Function TempPath(ByVal name)
  TempPath = fso.BuildPath(fixtureDir, "__tmp_" & fso.GetBaseName(name) & "_" & Timestamp() & "." & fso.GetExtensionName(name))
End Function

Function ManualTypes()
  ManualTypes = "dimension;limit-deviation;geometric-tolerance;datum;surface-roughness;text;flag-note;noa;annotation-view;capture"
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

Function Timestamp()
  Dim n: n = Now
  Timestamp = Year(n) & Right("0" & Month(n), 2) & Right("0" & Day(n), 2) & "_" & Right("0" & Hour(n), 2) & Right("0" & Minute(n), 2) & Right("0" & Second(n), 2)
End Function

Function RuntimeText(): RuntimeText = "V" & cfg.Version & "R" & cfg.Release & "SP" & cfg.ServicePack: End Function
Sub Fatal(ByVal message, ByVal code)
  WScript.Echo "[ERROR] " & message
  On Error Resume Next
  If Not ledger Is Nothing Then ledger.Close
  If Not catia Is Nothing Then catia.Quit
  WScript.Quit code
End Sub
