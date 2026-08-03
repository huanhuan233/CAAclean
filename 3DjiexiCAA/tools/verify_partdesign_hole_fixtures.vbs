Option Explicit

' Independently verifies saved CATParts through CATIA V5R21 Automation.
' Native Hole evidence comes from the Hole-specific properties, never from its display name.

Const CAT_COUNTERBORED_HOLE = 2
Const CAT_THREADED_HOLE = 0
Const CAT_UP_TO_LAST_LIMIT = 2

Dim fso, fixtureDir, reportPath, reportFile
Dim catia, cfg, doc, exitCode
Dim runtimeRelease, runtimeServicePack

exitCode = 1
Set fso = CreateObject("Scripting.FileSystemObject")
Set catia = Nothing
Set cfg = Nothing
Set doc = Nothing
Set reportFile = Nothing

If WScript.Arguments.Count <> 2 Then
  WScript.Echo "Usage: cscript //nologo verify_partdesign_hole_fixtures.vbs <fixture-directory> <report-file>"
  WScript.Quit 2
End If

fixtureDir = fso.GetAbsolutePathName(WScript.Arguments(0))
reportPath = fso.GetAbsolutePathName(WScript.Arguments(1))
If Not fso.FolderExists(fixtureDir) Then Fail "Fixture directory does not exist", 3

On Error Resume Next
Set reportFile = fso.CreateTextFile(reportPath, True, False)
RequireSuccess "Create verification report"

WScript.Echo "[CATIA] Starting independent verification instance"
Err.Clear
Set catia = CreateObject("CATIA.Application")
RequireSuccess "CreateObject(CATIA.Application)"
catia.Visible = False
catia.DisplayFileAlerts = False
Set cfg = catia.SystemConfiguration
RequireSuccess "Read SystemConfiguration"
runtimeRelease = cfg.Release
runtimeServicePack = cfg.ServicePack
WriteProperty "runtime.version", CStr(cfg.Version)
WriteProperty "runtime.release", CStr(runtimeRelease)
WriteProperty "runtime.service_pack", CStr(runtimeServicePack)
WriteProperty "runtime.value_source", "CATIA.SystemConfiguration"
If cfg.Version <> 5 Or runtimeRelease <> 21 Then Fail "Expected CATIA V5R21", 4

VerifyUpdated fso.BuildPath(fixtureDir, "partdesign_holes_updated.CATPart")
VerifyStale fso.BuildPath(fixtureDir, "partdesign_holes_stale.CATPart")

reportFile.Close
Set reportFile = Nothing
catia.Quit
Set catia = Nothing
WScript.Echo "[DONE] Independent saved-file verification passed"
exitCode = 0
WScript.Quit exitCode

' Verifies feature kinds, Hole properties, update state, and solid volume in the updated file.
Sub VerifyUpdated(ByVal filePath)
  On Error Resume Next
  Dim part, body, sketches, i, featureNames, featureObject, origins, originKey
  Dim padCount, pocketCount, holeCount, volume
  Dim blindHole, throughHole, counterboreHole, threadedHole, coolingPort, pocketControl

  If Not fso.FileExists(filePath) Then Fail "Missing updated fixture", 5
  WScript.Echo "[OPEN] " & fso.GetFileName(filePath)
  Err.Clear
  Set doc = catia.Documents.Open(filePath)
  RequireSuccess "Open updated fixture"
  Set part = doc.Part
  Set body = part.Bodies.Item("PartBody")
  RequireSuccess "Find updated PartBody"
  Set sketches = body.Sketches
  WScript.Echo "[HISTORY] updated top-level shapes=" & body.Shapes.Count & " top-level sketches=" & sketches.Count
  For i = 1 To body.Shapes.Count
    WScript.Echo "[TREE] shape[" & i & "]=" & body.Shapes.Item(i).Name & "|" & TypeName(body.Shapes.Item(i))
  Next

  Set featureObject = part.FindObjectByName("Pad_Base")
  WScript.Echo "[TYPE] Pad_Base=" & TypeName(featureObject) & " prism_limit=" & CStr(HasPrismLimit(featureObject)) & " direction_orientation=" & featureObject.DirectionOrientation
  If TypeName(featureObject) <> "Pad" Or Not HasPrismLimit(featureObject) Then Fail "Pad_Base is not a native Pad", 7
  padCount = 1

  Set pocketControl = part.FindObjectByName("Pocket_Control")
  WScript.Echo "[TYPE] Pocket_Control=" & TypeName(pocketControl) & " prism_limit=" & CStr(HasPrismLimit(pocketControl)) & " direction_orientation=" & pocketControl.DirectionOrientation
  If TypeName(pocketControl) <> "Pocket" Or Not HasPrismLimit(pocketControl) Then Fail "Pocket_Control is not a native Pocket", 7
  pocketCount = 1

  holeCount = 0
  Set origins = CreateObject("Scripting.Dictionary")
  featureNames = Array("Hole_Blind", "Hole_Through", "Hole_Counterbore", "Hole_Threaded", "CoolingPort_A")
  For i = 0 To UBound(featureNames)
    Set featureObject = part.FindObjectByName(featureNames(i))
    If Not IsNativeHole(featureObject) Then Fail featureNames(i) & " lacks the native Hole interface", 7
    If GetHoleDirectionZ(featureObject) < 0.9 Then Fail featureNames(i) & " does not point into Pad_Base", 7
    originKey = GetHoleOriginKey(featureObject)
    If origins.Exists(originKey) Then Fail "Two Holes share the same origin: " & originKey, 7
    origins.Add originKey, featureNames(i)
    holeCount = holeCount + 1
    PrintHoleEvidence featureObject
  Next

  Set blindHole = part.FindObjectByName("Hole_Blind")
  If Not IsNativeHole(blindHole) Then Fail "Hole_Blind lacks the native Hole interface", 8
  If blindHole.BottomLimit.LimitMode <> 0 Then Fail "Hole_Blind is not an offset/blind Hole", 8
  If Abs(blindHole.BottomLimit.Dimension.Value - 12) > 0.001 Then Fail "Hole_Blind depth is not 12 mm", 8

  Set throughHole = part.FindObjectByName("Hole_Through")
  If Not IsNativeHole(throughHole) Then Fail "Hole_Through lacks the native Hole interface", 8
  If throughHole.BottomLimit.LimitMode <> CAT_UP_TO_LAST_LIMIT Then Fail "Hole_Through is not Up To Last", 8

  Set counterboreHole = part.FindObjectByName("Hole_Counterbore")
  If Not IsNativeHole(counterboreHole) Then Fail "Hole_Counterbore lacks the native Hole interface", 8
  If counterboreHole.Type <> CAT_COUNTERBORED_HOLE Then Fail "Hole_Counterbore native type is not counterbored", 8
  If Abs(counterboreHole.HeadDiameter.Value - 18) > 0.001 Then Fail "Counterbore head diameter is not 18 mm", 8
  If Abs(counterboreHole.HeadDepth.Value - 5) > 0.001 Then Fail "Counterbore head depth is not 5 mm", 8

  Set threadedHole = part.FindObjectByName("Hole_Threaded")
  If Not IsNativeHole(threadedHole) Then Fail "Hole_Threaded lacks the native Hole interface", 8
  If threadedHole.ThreadingMode <> CAT_THREADED_HOLE Then Fail "Hole_Threaded native threading is disabled", 8
  If threadedHole.ThreadDepth.Value <= 0 Or threadedHole.ThreadPitch.Value <= 0 Then Fail "Hole_Threaded has invalid native thread dimensions", 8

  Set coolingPort = part.FindObjectByName("CoolingPort_A")
  If Not IsNativeHole(coolingPort) Then Fail "CoolingPort_A lacks the native Hole interface", 8
  WScript.Echo "[NATIVE] CoolingPort_A exposes Diameter, Type, BottomLimit and ThreadingMode"

  If IsNativeHole(pocketControl) Then Fail "Pocket_Control was incorrectly accepted as a Hole", 9
  If pocketControl.DirectionOrientation <> 0 Then Fail "Pocket_Control does not point into Pad_Base", 9
  WScript.Echo "[NEGATIVE] Pocket_Control is Pocket and fails native Hole probing"

  Set featureObject = part.FindObjectByName("Sketch_Base")
  If TypeName(featureObject) <> "Sketch" Then Fail "Sketch_Base is missing or not native", 10
  Set featureObject = part.FindObjectByName("Sketch_Pocket")
  If TypeName(featureObject) <> "Sketch" Then Fail "Sketch_Pocket is missing or not native", 10

  featureNames = Array("Sketch_Base", "Pad_Base", "Hole_Blind", "Hole_Through", "Hole_Counterbore", "Hole_Threaded", "CoolingPort_A", "Sketch_Pocket", "Pocket_Control")
  For i = 0 To UBound(featureNames)
    Set featureObject = part.FindObjectByName(featureNames(i))
    If Not part.IsUpToDate(featureObject) Then Fail "Updated object is stale: " & featureNames(i), 6
  Next

  volume = GetFinalResultVolume(doc, part)
  If volume <= 0 Then Fail "PartBody has no positive solid volume", 11
  If volume >= 450000 Then Fail "Subtractive features did not reduce the 450000 mm3 Pad_Base volume", 11
  If volume >= 447800 Then Fail "Hole removals did not reduce the solid beyond the 7 mm Pocket volume", 11
  WScript.Echo "[SOLID] PartBody volume_mm3=" & NumberText(volume)

  WriteProperty "updated.pad_count", CStr(padCount)
  WriteProperty "updated.pocket_count", CStr(pocketCount)
  WriteProperty "updated.hole_count", CStr(holeCount)
  WriteProperty "updated.sketch_count", CStr(sketches.Count)
  WriteProperty "updated.all_up_to_date", "true"
  WriteProperty "updated.cooling_port_native_hole", "true"
  WriteProperty "updated.pocket_rejected_as_hole", "true"
  WriteProperty "updated.blind_hole", "true"
  WriteProperty "updated.through_hole", "true"
  WriteProperty "updated.counterbore_hole", "true"
  WriteProperty "updated.threaded_hole", "true"
  WriteProperty "updated.solid_volume_mm3", NumberText(volume)

  Err.Clear
  doc.Close
  RequireSuccess "Close updated fixture"
  Set doc = Nothing
End Sub

' Verifies that the stale file remains healthy while persisting at least one real stale object.
Sub VerifyStale(ByVal filePath)
  On Error Resume Next
  Dim part, body, i, staleCount, staleNames, featureNames, featureObject
  If Not fso.FileExists(filePath) Then Fail "Missing stale fixture", 12
  WScript.Echo "[OPEN] " & fso.GetFileName(filePath)
  Err.Clear
  Set doc = catia.Documents.Open(filePath)
  RequireSuccess "Open stale fixture"
  Set part = doc.Part
  Set body = part.Bodies.Item("PartBody")
  RequireSuccess "Find stale PartBody"
  WScript.Echo "[HISTORY] stale top-level shapes=" & body.Shapes.Count & " top-level sketches=" & body.Sketches.Count

  staleCount = 0
  staleNames = ""
  featureNames = Array("Sketch_Base", "Pad_Base", "Hole_Blind", "Hole_Through", "Hole_Counterbore", "Hole_Threaded", "CoolingPort_A", "Sketch_Pocket", "Pocket_Control")
  For i = 0 To UBound(featureNames)
    Err.Clear
    Set featureObject = part.FindObjectByName(featureNames(i))
    RequireSuccess "Find stale history object: " & featureNames(i)
    If Not part.IsUpToDate(featureObject) Then
      staleCount = staleCount + 1
      If Len(staleNames) > 0 Then staleNames = staleNames & ";"
      staleNames = staleNames & featureObject.Name & "|" & TypeName(featureObject)
      WScript.Echo "[STALE] " & featureObject.Name & " | " & TypeName(featureObject) & " | Part.IsUpToDate=False"
    End If
  Next
  If staleCount < 1 Then Fail "No persisted stale object was found", 14

  If Not IsNativeHole(part.FindObjectByName("CoolingPort_A")) Then Fail "Stale fixture lost CoolingPort_A native Hole", 15
  If TypeName(part.FindObjectByName("Pocket_Control")) <> "Pocket" Then Fail "Stale fixture lost Pocket_Control", 15

  WriteProperty "stale.object_count", CStr(staleCount)
  WriteProperty "stale.objects", staleNames
  WriteProperty "stale.status_source", "Part.IsUpToDate"
  WriteProperty "stale.main_history_present", "true"

  Err.Clear
  doc.Close
  RequireSuccess "Close stale fixture"
  Set doc = Nothing
End Sub

' Probes the dedicated Hole Automation contract without consulting the object name.
Function IsNativeHole(ByVal candidate)
  On Error Resume Next
  Dim diameterValue, nativeType, limitMode, threadingMode
  Err.Clear
  diameterValue = candidate.Diameter.Value
  nativeType = candidate.Type
  limitMode = candidate.BottomLimit.LimitMode
  threadingMode = candidate.ThreadingMode
  IsNativeHole = (Err.Number = 0)
  Err.Clear
End Function

' Probes the common native Pad/Pocket prism limit contract.
Function HasPrismLimit(ByVal candidate)
  On Error Resume Next
  Dim depthValue
  Err.Clear
  depthValue = candidate.FirstLimit.Dimension.Value
  HasPrismLimit = (Err.Number = 0)
  Err.Clear
End Function

' Reports the Hole-specific properties that prove each counted object is native.
Sub PrintHoleEvidence(ByVal hole)
  On Error Resume Next
  Dim threadText, detailText
  threadText = "smooth"
  If hole.ThreadingMode = CAT_THREADED_HOLE Then threadText = "threaded"
  detailText = " | depth_mm=" & NumberText(hole.BottomLimit.Dimension.Value)
  If hole.Type = CAT_COUNTERBORED_HOLE Then
    detailText = detailText & " | head_diameter_mm=" & NumberText(hole.HeadDiameter.Value) & " | head_depth_mm=" & NumberText(hole.HeadDepth.Value)
  End If
  If hole.ThreadingMode = CAT_THREADED_HOLE Then
    detailText = detailText & " | thread_diameter_mm=" & NumberText(hole.ThreadDiameter.Value) & _
      " | thread_depth_mm=" & NumberText(hole.ThreadDepth.Value) & _
      " | thread_pitch_mm=" & NumberText(hole.ThreadPitch.Value) & _
      " | thread_description=" & hole.HoleThreadDescription.Value
  End If
  WScript.Echo "[HOLE] " & hole.Name & _
    " | type=" & hole.Type & _
    " | diameter_mm=" & NumberText(hole.Diameter.Value) & _
    " | origin=" & GetHoleOriginKey(hole) & _
    " | direction=" & GetHoleDirectionKey(hole) & _
    " | limit_mode=" & hole.BottomLimit.LimitMode & _
    " | threading=" & threadText & detailText
End Sub

' Returns the dedicated Hole origin as a deterministic coordinate key.
Function GetHoleOriginKey(ByVal hole)
  On Error Resume Next
  Dim coordinates(2)
  Err.Clear
  hole.GetOrigin coordinates
  RequireSuccess "Read native Hole origin: " & hole.Name
  GetHoleOriginKey = NumberText(coordinates(0)) & "," & NumberText(coordinates(1)) & "," & NumberText(coordinates(2))
End Function

' Returns the native Hole axis direction reported after reopening the saved file.
Function GetHoleDirectionKey(ByVal hole)
  On Error Resume Next
  Dim direction(2)
  Err.Clear
  hole.GetDirection direction
  RequireSuccess "Read native Hole direction: " & hole.Name
  GetHoleDirectionKey = NumberText(direction(0)) & "," & NumberText(direction(1)) & "," & NumberText(direction(2))
End Function

' Returns the Z component used to prove a bottom-plane Hole points into the positive-Z Pad.
Function GetHoleDirectionZ(ByVal hole)
  On Error Resume Next
  Dim direction(2)
  Err.Clear
  hole.GetDirection direction
  RequireSuccess "Read native Hole direction Z: " & hole.Name
  GetHoleDirectionZ = CDbl(direction(2))
End Function

' Measures the final Part product inertia to prove that all subtractive features affect the solid.
Function GetFinalResultVolume(ByVal partDoc, ByVal part)
  On Error Resume Next
  Dim analysis, volumeValue
  Err.Clear
  Set analysis = partDoc.Product.Analyze
  volumeValue = analysis.Volume
  RequireSuccess "Measure final Part product volume"
  GetFinalResultVolume = volumeValue
End Function

' Produces locale-independent decimal text for reports and JSON generation.
Function NumberText(ByVal value)
  NumberText = Replace(CStr(value), ",", ".")
End Function

' Writes one verified key/value pair consumed by the manifest builder.
Sub WriteProperty(ByVal key, ByVal value)
  On Error Resume Next
  reportFile.WriteLine key & "=" & value
  RequireSuccess "Write verification property: " & key
End Sub

' Converts the current Automation error into a nonzero verifier exit.
Sub RequireSuccess(ByVal stage)
  On Error Resume Next
  If Err.Number <> 0 Then
    Dim numberText, descriptionText
    numberText = "0x" & Hex(Err.Number)
    descriptionText = Err.Description
    Err.Clear
    Fail stage & " failed: " & numberText & " " & descriptionText, 20
  End If
  Err.Clear
End Sub

' Closes files and the owned CATIA instance after an unrecoverable verification error.
Sub Fail(ByVal message, ByVal code)
  On Error Resume Next
  WScript.Echo "[ERROR] " & message
  exitCode = code
  Err.Clear
  If Not doc Is Nothing Then doc.Close
  Err.Clear
  If Not reportFile Is Nothing Then reportFile.Close
  Err.Clear
  If Not catia Is Nothing Then catia.Quit
  On Error GoTo 0
  WScript.Quit exitCode
End Sub
