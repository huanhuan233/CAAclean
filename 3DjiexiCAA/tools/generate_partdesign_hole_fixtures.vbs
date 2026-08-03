Option Explicit

' Generates two CATIA V5R21 regression parts with real Part Design features.
' The script owns the CATIA instance it creates and always closes it.

Const CAT_SIMPLE_HOLE = 0
Const CAT_COUNTERBORED_HOLE = 2
Const CAT_THREADED_HOLE = 0
Const CAT_SMOOTH_HOLE = 1
Const CAT_RIGHT_THREAD = 0
Const CAT_UP_TO_LAST_LIMIT = 2
Const CAT_MANUAL_UPDATE = 0

Dim fso, outputDir, updatedPath, stalePath
Dim catia, cfg, doc, part, settingCtrl, originalUpdateMode
Dim ownsSettingState, exitCode

exitCode = 1
ownsSettingState = False
Set fso = CreateObject("Scripting.FileSystemObject")
Set catia = Nothing
Set cfg = Nothing
Set doc = Nothing
Set part = Nothing
Set settingCtrl = Nothing

If WScript.Arguments.Count <> 1 Then
  WScript.Echo "Usage: cscript //nologo generate_partdesign_hole_fixtures.vbs <output-directory>"
  WScript.Quit 2
End If

outputDir = fso.GetAbsolutePathName(WScript.Arguments(0))
EnsureFolder outputDir
updatedPath = fso.BuildPath(outputDir, "partdesign_holes_updated.CATPart")
stalePath = fso.BuildPath(outputDir, "partdesign_holes_stale.CATPart")

On Error Resume Next
DeleteIfExists updatedPath
DeleteIfExists stalePath

WScript.Echo "[CATIA] Starting CATIA.Application"
Err.Clear
Set catia = CreateObject("CATIA.Application")
RequireSuccess "CreateObject(CATIA.Application)"
catia.Visible = False
catia.DisplayFileAlerts = False

Err.Clear
Set cfg = catia.SystemConfiguration
RequireSuccess "Read SystemConfiguration"
WScript.Echo "[CATIA] Runtime V" & cfg.Version & "R" & cfg.Release & " SP" & cfg.ServicePack
If cfg.Version <> 5 Or cfg.Release <> 21 Then Fail "Expected CATIA V5R21", 3

WScript.Echo "[BUILD] Creating native Part Design history"
Set doc = catia.Documents.Add("Part")
RequireSuccess "Documents.Add(Part)"
BuildUpdatedPart doc
Set part = doc.Part

Err.Clear
part.Update
RequireSuccess "Part.Update(updated)"
Err.Clear
AssertAllDesignShapesUpToDate part, "updated in-memory document"

Err.Clear
doc.SaveAs updatedPath
RequireSuccess "SaveAs(updated)"
Err.Clear
doc.Close
RequireSuccess "Close(updated after save)"
Set doc = Nothing

WScript.Echo "[VERIFY] Reopening updated fixture"
Err.Clear
Set doc = catia.Documents.Open(updatedPath)
RequireSuccess "Open(updated)"
Set part = doc.Part
Err.Clear
VerifyRequiredHistory part, True
Err.Clear
doc.Close
RequireSuccess "Close(reopened updated)"
Set doc = Nothing

WScript.Echo "[STALE] Switching Part Infrastructure update mode to manual"
Err.Clear
Set settingCtrl = catia.SettingControllers.Item("CATMmuPartInfrastructureSettingCtrl")
RequireSuccess "Get CATMmuPartInfrastructureSettingCtrl"
Err.Clear
originalUpdateMode = settingCtrl.UpdateMode
settingCtrl.UpdateMode = CAT_MANUAL_UPDATE
RequireSuccess "Set manual update mode"
ownsSettingState = True

Err.Clear
Set doc = catia.Documents.Open(updatedPath)
RequireSuccess "Open(updated for stale copy)"
Set part = doc.Part
Dim stalePad
Set stalePad = part.FindObjectByName("Pad_Base")
RequireSuccess "Find Pad_Base for stale edit"
Err.Clear
stalePad.FirstLimit.Dimension.Value = 27
RequireSuccess "Change Pad_Base length without update"
If part.IsUpToDate(stalePad) Then Fail "Pad_Base unexpectedly remains up-to-date after manual edit", 4

Err.Clear
doc.SaveAs stalePath
RequireSuccess "SaveAs(stale)"
Err.Clear
doc.Close
RequireSuccess "Close(stale after save)"
Set doc = Nothing

WScript.Echo "[VERIFY] Reopening stale fixture while manual update is active"
Err.Clear
Set doc = catia.Documents.Open(stalePath)
RequireSuccess "Open(stale)"
Set part = doc.Part
Err.Clear
VerifyRequiredHistory part, False
Err.Clear
If CountStaleShapes(part) < 1 Then Fail "No persisted not-up-to-date design shape was found", 5
Err.Clear
doc.Close
RequireSuccess "Close(reopened stale)"
Set doc = Nothing

Err.Clear
settingCtrl.UpdateMode = originalUpdateMode
RequireSuccess "Restore original update mode"
ownsSettingState = False

WScript.Echo "[DONE] " & updatedPath
WScript.Echo "[DONE] " & stalePath
exitCode = 0
CleanupAndQuit
WScript.Quit exitCode

' Builds the complete native Part Design model used by the updated fixture.
Sub BuildUpdatedPart(ByVal partDoc)
  On Error Resume Next
  Dim localPart, bodies, body, sketches, originElements, planeRef
  Dim baseSketch, factory2D, shapeFactory, pad, positionSketch
  Dim holeBlind, holeThrough, holeCounterbore, holeThreaded, coolingPort
  Dim pocketSketch, pocketFactory, pocket

  Set localPart = partDoc.Part
  Set bodies = localPart.Bodies
  If bodies.Count = 0 Then
    Set body = bodies.Add()
  Else
    Set body = bodies.Item(1)
  End If
  body.Name = "PartBody"
  localPart.InWorkObject = body

  Set sketches = body.Sketches
  Set originElements = localPart.OriginElements
  Set planeRef = localPart.CreateReferenceFromObject(originElements.PlaneXY)
  Set baseSketch = sketches.Add(planeRef)
  RequireSuccess "Create Sketch_Base"
  baseSketch.Name = "Sketch_Base"
  Set factory2D = baseSketch.OpenEdition()
  factory2D.CreateLine -90, -50, 90, -50
  factory2D.CreateLine 90, -50, 90, 50
  factory2D.CreateLine 90, 50, -90, 50
  factory2D.CreateLine -90, 50, -90, -50
  baseSketch.CloseEdition
  RequireSuccess "Close Sketch_Base edition"

  Set shapeFactory = localPart.ShapeFactory
  Set pad = shapeFactory.AddNewPad(baseSketch, 25)
  RequireSuccess "Create Pad_Base"
  pad.Name = "Pad_Base"
  localPart.Update
  RequireSuccess "Update Pad_Base"

  Set positionSketch = CreatePointSketch(sketches, planeRef, "Position_Hole_Blind", -65, -25)
  Set holeBlind = shapeFactory.AddNewHoleFromSketch(positionSketch, 12)
  RequireSuccess "Create Hole_Blind"
  holeBlind.Reverse
  RequireSuccess "Orient Hole_Blind into Pad_Base"
  holeBlind.Name = "Hole_Blind"
  holeBlind.Type = CAT_SIMPLE_HOLE
  holeBlind.ThreadingMode = CAT_SMOOTH_HOLE
  holeBlind.BottomLimit.LimitMode = 0
  holeBlind.BottomLimit.Dimension.Value = 12
  holeBlind.Diameter.Value = 10
  localPart.UpdateObject holeBlind
  RequireSuccess "Update Hole_Blind"

  Set positionSketch = CreatePointSketch(sketches, planeRef, "Position_Hole_Through", -30, -25)
  Set holeThrough = shapeFactory.AddNewHoleFromSketch(positionSketch, 25)
  RequireSuccess "Create Hole_Through"
  holeThrough.Reverse
  RequireSuccess "Orient Hole_Through into Pad_Base"
  holeThrough.Name = "Hole_Through"
  holeThrough.Type = CAT_SIMPLE_HOLE
  holeThrough.ThreadingMode = CAT_SMOOTH_HOLE
  holeThrough.Diameter.Value = 10
  holeThrough.BottomLimit.LimitMode = CAT_UP_TO_LAST_LIMIT
  localPart.UpdateObject holeThrough
  RequireSuccess "Update Hole_Through"

  Set positionSketch = CreatePointSketch(sketches, planeRef, "Position_Hole_Counterbore", 5, -25)
  Set holeCounterbore = shapeFactory.AddNewHoleFromSketch(positionSketch, 15)
  RequireSuccess "Create Hole_Counterbore"
  holeCounterbore.Reverse
  RequireSuccess "Orient Hole_Counterbore into Pad_Base"
  holeCounterbore.Name = "Hole_Counterbore"
  holeCounterbore.Type = CAT_COUNTERBORED_HOLE
  holeCounterbore.ThreadingMode = CAT_SMOOTH_HOLE
  holeCounterbore.BottomLimit.LimitMode = 0
  holeCounterbore.BottomLimit.Dimension.Value = 15
  holeCounterbore.Diameter.Value = 10
  holeCounterbore.HeadDiameter.Value = 18
  holeCounterbore.HeadDepth.Value = 5
  localPart.UpdateObject holeCounterbore
  RequireSuccess "Update Hole_Counterbore"

  Set positionSketch = CreatePointSketch(sketches, planeRef, "Position_Hole_Threaded", 40, -25)
  Set holeThreaded = shapeFactory.AddNewHoleFromSketch(positionSketch, 15)
  RequireSuccess "Create Hole_Threaded"
  holeThreaded.Reverse
  RequireSuccess "Orient Hole_Threaded into Pad_Base"
  holeThreaded.Name = "Hole_Threaded"
  holeThreaded.Type = CAT_SIMPLE_HOLE
  holeThreaded.BottomLimit.LimitMode = 0
  holeThreaded.Diameter.Value = 8.5
  holeThreaded.ThreadingMode = CAT_THREADED_HOLE
  holeThreaded.ThreadSide = CAT_RIGHT_THREAD
  holeThreaded.CreateStandardThreadDesignTable 1
  RequireSuccess "Enable native metric threading on Hole_Threaded"
  SetThreadDescriptionIfAvailable holeThreaded, "M10"
  holeThreaded.BottomLimit.Dimension.Value = 15
  localPart.UpdateObject holeThreaded
  RequireSuccess "Update Hole_Threaded"

  Set positionSketch = CreatePointSketch(sketches, planeRef, "Position_CoolingPort_A", 70, 20)
  Set coolingPort = shapeFactory.AddNewHoleFromSketch(positionSketch, 12)
  RequireSuccess "Create renamed native Hole"
  coolingPort.Reverse
  RequireSuccess "Orient CoolingPort_A into Pad_Base"
  coolingPort.Name = "CoolingPort_A"
  coolingPort.Type = CAT_SIMPLE_HOLE
  coolingPort.ThreadingMode = CAT_SMOOTH_HOLE
  coolingPort.BottomLimit.LimitMode = 0
  coolingPort.BottomLimit.Dimension.Value = 12
  coolingPort.Diameter.Value = 9
  localPart.UpdateObject coolingPort
  RequireSuccess "Update CoolingPort_A"

  localPart.InWorkObject = body
  Set pocketSketch = sketches.Add(planeRef)
  RequireSuccess "Create Sketch_Pocket"
  pocketSketch.Name = "Sketch_Pocket"
  Set pocketFactory = pocketSketch.OpenEdition()
  pocketFactory.CreateClosedCircle 0, 25, 10
  pocketSketch.CloseEdition
  RequireSuccess "Close Sketch_Pocket edition"
  Set pocket = shapeFactory.AddNewPocket(pocketSketch, 7)
  RequireSuccess "Create Pocket_Control"
  pocket.Name = "Pocket_Control"
  pocket.DirectionOrientation = 0
  RequireSuccess "Orient Pocket_Control into Pad_Base"
  localPart.UpdateObject pocket
  RequireSuccess "Update Pocket_Control"

  localPart.Update
  RequireSuccess "Final Part.Update"
End Sub

' Creates the one-point positioning sketch required by AddNewHoleFromSketch.
Function CreatePointSketch(ByVal sketches, ByVal supportRef, ByVal sketchName, ByVal x, ByVal y)
  On Error Resume Next
  Dim sketch, pointFactory
  Err.Clear
  Set sketch = sketches.Add(supportRef)
  RequireSuccess "Create " & sketchName
  sketch.Name = sketchName
  Set pointFactory = sketch.OpenEdition()
  pointFactory.CreatePoint x, y
  sketch.CloseEdition
  RequireSuccess "Close " & sketchName & " edition"
  Set CreatePointSketch = sketch
End Function

' Applies a named metric thread designation when the R21 design table exposes it.
Sub SetThreadDescriptionIfAvailable(ByVal hole, ByVal description)
  On Error Resume Next
  Dim threadDescription
  Err.Clear
  Set threadDescription = hole.HoleThreadDescription
  If Err.Number = 0 And Not threadDescription Is Nothing Then
    threadDescription.Value = description
    If Err.Number <> 0 Then
      WScript.Echo "[THREAD] Design table kept its default metric designation: " & Err.Description
      Err.Clear
    End If
  Else
    WScript.Echo "[THREAD] Description parameter unavailable; native ThreadingMode remains enabled"
    Err.Clear
  End If
End Sub

' Verifies the required history through dedicated Part Design Automation properties.
Sub VerifyRequiredHistory(ByVal localPart, ByVal expectAllUpdated)
  On Error Resume Next
  Dim body, pad, pocket, holeNames, i, hole, dummy
  Set body = localPart.Bodies.Item("PartBody")
  RequireSuccess "Verify PartBody"
  Set pad = localPart.FindObjectByName("Pad_Base")
  dummy = pad.FirstLimit.Dimension.Value
  RequireSuccess "Verify native Pad_Base interface"
  Set pocket = localPart.FindObjectByName("Pocket_Control")
  dummy = pocket.FirstLimit.Dimension.Value
  RequireSuccess "Verify native Pocket_Control interface"

  holeNames = Array("Hole_Blind", "Hole_Through", "Hole_Counterbore", "Hole_Threaded", "CoolingPort_A")
  For i = 0 To UBound(holeNames)
    Set hole = localPart.FindObjectByName(holeNames(i))
    dummy = hole.Diameter.Value
    dummy = hole.Type
    dummy = hole.BottomLimit.LimitMode
    RequireSuccess "Verify native Hole interface: " & holeNames(i)
  Next
  If localPart.FindObjectByName("Hole_Blind").BottomLimit.LimitMode <> 0 Then Fail "Hole_Blind is not a blind offset hole", 7
  If localPart.FindObjectByName("Hole_Through").BottomLimit.LimitMode <> CAT_UP_TO_LAST_LIMIT Then Fail "Hole_Through is not Up To Last", 7
  If localPart.FindObjectByName("Hole_Counterbore").Type <> CAT_COUNTERBORED_HOLE Then Fail "Hole_Counterbore has the wrong native type", 7
  If localPart.FindObjectByName("Hole_Threaded").ThreadingMode <> CAT_THREADED_HOLE Then Fail "Hole_Threaded is not natively threaded", 7
  If expectAllUpdated Then AssertAllDesignShapesUpToDate localPart, "reopened updated fixture"
End Sub

' Ensures every shape in PartBody is calculated with the latest specifications.
Sub AssertAllDesignShapesUpToDate(ByVal localPart, ByVal context)
  On Error Resume Next
  Dim body, shapes, sketches, i
  Set body = localPart.Bodies.Item("PartBody")
  Set shapes = body.Shapes
  For i = 1 To shapes.Count
    If Not localPart.IsUpToDate(shapes.Item(i)) Then
      Fail "Unexpected stale shape in " & context & ": " & shapes.Item(i).Name, 8
    End If
  Next
  Set sketches = body.Sketches
  For i = 1 To sketches.Count
    If Not localPart.IsUpToDate(sketches.Item(i)) Then
      Fail "Unexpected stale sketch in " & context & ": " & sketches.Item(i).Name, 8
    End If
  Next
End Sub

' Counts persisted stale Part Design shapes and prints their names and Automation type names.
Function CountStaleShapes(ByVal localPart)
  On Error Resume Next
  Dim body, shapes, i, count
  count = 0
  Set body = localPart.Bodies.Item("PartBody")
  Set shapes = body.Shapes
  For i = 1 To shapes.Count
    If Not localPart.IsUpToDate(shapes.Item(i)) Then
      count = count + 1
      WScript.Echo "[STALE] " & shapes.Item(i).Name & " | " & TypeName(shapes.Item(i)) & " | Part.IsUpToDate=False"
    End If
  Next
  CountStaleShapes = count
End Function

' Creates all missing folders in an absolute output path.
Sub EnsureFolder(ByVal folderPath)
  On Error Resume Next
  Dim parentPath
  If fso.FolderExists(folderPath) Then Exit Sub
  parentPath = fso.GetParentFolderName(folderPath)
  If Len(parentPath) > 0 And Not fso.FolderExists(parentPath) Then EnsureFolder parentPath
  fso.CreateFolder folderPath
End Sub

' Removes only a previous generated fixture at the exact requested path.
Sub DeleteIfExists(ByVal filePath)
  On Error Resume Next
  If fso.FileExists(filePath) Then fso.DeleteFile filePath, True
  RequireSuccess "Delete previous fixture: " & fso.GetFileName(filePath)
End Sub

' Turns the current Automation error into a fatal, traceable generator failure.
Sub RequireSuccess(ByVal stage)
  On Error Resume Next
  If Err.Number <> 0 Then
    Dim numberText, descriptionText
    numberText = "0x" & Hex(Err.Number)
    descriptionText = Err.Description
    Err.Clear
    Fail stage & " failed: " & numberText & " " & descriptionText, 20
  End If
End Sub

' Reports an unrecoverable generation failure, cleans up, and exits nonzero.
Sub Fail(ByVal message, ByVal code)
  On Error Resume Next
  WScript.Echo "[ERROR] " & message
  exitCode = code
  CleanupAndQuit
  Err.Clear
  If Len(updatedPath) > 0 And fso.FileExists(updatedPath) Then fso.DeleteFile updatedPath, True
  Err.Clear
  If Len(stalePath) > 0 And fso.FileExists(stalePath) Then fso.DeleteFile stalePath, True
  On Error GoTo 0
  WScript.Quit exitCode
End Sub

' Closes open documents, restores the user setting, and terminates the owned CATIA process.
Sub CleanupAndQuit()
  On Error Resume Next
  Err.Clear
  If Not doc Is Nothing Then doc.Close
  Err.Clear
  If ownsSettingState And Not settingCtrl Is Nothing Then settingCtrl.UpdateMode = originalUpdateMode
  Err.Clear
  If Not catia Is Nothing Then catia.Quit
  Err.Clear
End Sub
