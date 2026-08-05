Option Explicit

' Attempts to build the negative FTA fixture from its scaffold. The script only
' promotes a temp CATPart after it can be saved, closed, and reopened. Unsupported
' invalid-reference states are logged as BLOCKED instead of being faked.

Dim fso, fixtureDir, scaffoldPath, formalPath, tmpPath, catia, cfg, doc, part, annSet, annFactory, userSurfaces
Dim messages, changed
Set fso = CreateObject("Scripting.FileSystemObject")
If WScript.Arguments.Count = 1 And LCase(WScript.Arguments(0)) = "--syntax-check" Then
  WScript.Echo "[SYNTAX-OK] build_fta_orphan_invalid.vbs"
  WScript.Quit 0
End If
If WScript.Arguments.Count <> 1 Then
  WScript.Echo "Usage: cscript //nologo build_fta_orphan_invalid.vbs <fixture-directory>"
  WScript.Quit 2
End If

fixtureDir = fso.GetAbsolutePathName(WScript.Arguments(0))
scaffoldPath = fso.BuildPath(fixtureDir, "fta_orphan_invalid_scaffold.CATPart")
formalPath = fso.BuildPath(fixtureDir, "fta_orphan_invalid.CATPart")
tmpPath = fso.BuildPath(fixtureDir, "_tmp_fta_orphan_invalid.CATPart")
If Not fso.FileExists(scaffoldPath) Then WScript.Echo "[ERROR] Missing scaffold " & scaffoldPath: WScript.Quit 3
If fso.FileExists(tmpPath) Then fso.DeleteFile tmpPath, True

Set catia = CreateCatia()
catia.Visible = True
catia.DisplayFileAlerts = False
Set cfg = catia.SystemConfiguration
If cfg.Version <> 5 Or cfg.Release <> 21 Then Fatal "Expected CATIA V5R21, got " & RuntimeText(), 4

Set doc = catia.Documents.Open(scaffoldPath)
doc.SaveAs tmpPath
Set part = doc.Part
Set annSet = EnsureAnnotationSet()
Set annFactory = annSet.AnnotationFactory
Set userSurfaces = part.UserSurfaces
messages = "": changed = False

AddTextOnFace "ORPHAN_VALID_BASE", "valid base annotation before invalid-reference attempts"
AddTextOnFace "ORPHAN_DELETED_FACE", "candidate orphan annotation"
AttemptDeletedFaceOrphan
AttemptSuppressedFeature
AttemptInvalidGdt
AttemptInvalidViewCapture

doc.Save
doc.Close
If Not ReopenHasAnnotationSet(tmpPath) Then
  WScript.Echo "[BLOCKED] temp orphan fixture did not reopen with AnnotationSets.Count > 0"
  catia.Quit
  WScript.Quit 5
End If

If fso.FileExists(formalPath) Then
  Dim backupPath
  backupPath = fso.BuildPath(fixtureDir, "repair_backups\fta_orphan_invalid_" & TimestampText() & ".CATPart")
  EnsureFolder fso.GetParentFolderName(backupPath)
  fso.CopyFile formalPath, backupPath, True
  WScript.Echo "[BACKUP] " & backupPath
  fso.DeleteFile formalPath, True
End If
fso.MoveFile tmpPath, formalPath
catia.Quit
WScript.Echo "[DONE] fta_orphan_invalid formal carrier written; invalid states may remain BLOCKED per verifier"
WScript.Quit 0

Sub AddTextOnFace(ByVal objectName, ByVal textValue)
  If HasAnnotation(objectName) Then WScript.Echo "[SKIP] " & objectName: Exit Sub
  Dim ref, us, ann, txt, e, d
  Set ref = PadFaceRef(2)
  If ObjectIsNothing(ref) Then WScript.Echo "[BLOCKED] " & objectName & " face reference unavailable": Exit Sub
  Err.Clear
  On Error Resume Next
  Set us = userSurfaces.Generate(ref)
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
  If e <> 0 Then WScript.Echo "[COM-ERROR] " & objectName & " set text/name 0x" & Hex(e) & " " & d: Exit Sub
  changed = True
  WScript.Echo "[ADDED] " & objectName
End Sub

Sub AttemptDeletedFaceOrphan()
  Dim sel, pad, e, d
  Err.Clear
  On Error Resume Next
  Set pad = part.Bodies.Item(1).Shapes.Item("Pad_FTA_Carrier")
  Set sel = doc.Selection
  sel.Clear
  sel.Add pad
  sel.Delete
  part.Update
  e = Err.Number: d = Err.Description
  On Error GoTo 0
  If e <> 0 Then
    WScript.Echo "[BLOCKED] ORPHAN_DELETED_FACE CATIA rejected deleting referenced final face 0x" & Hex(e) & " " & d
    Err.Clear
  Else
    WScript.Echo "[ATTEMPTED] ORPHAN_DELETED_FACE deleted referenced Pad_FTA_Carrier; reopen verifier must decide"
    changed = True
  End If
End Sub

Sub AttemptSuppressedFeature()
  WScript.Echo "[BLOCKED] ORPHAN_SUPPRESSED_FEATURE no reliable V5R21 Automation suppression API found for PartDesign feature with retained broken FTA link"
End Sub

Sub AttemptInvalidGdt()
  Dim ref, us, ann, e, d
  Set ref = PadFaceRef(2)
  If ObjectIsNothing(ref) Then WScript.Echo "[BLOCKED] INVALID_GDT no remaining face support after orphan attempt": Exit Sub
  Err.Clear
  On Error Resume Next
  Set us = userSurfaces.Generate(ref)
  Set ann = annFactory.CreateToleranceWithDRF(999, us, Nothing)
  e = Err.Number: d = Err.Description
  On Error GoTo 0
  If e <> 0 Or ObjectIsNothing(ann) Then
    WScript.Echo "[BLOCKED] INVALID_GDT CATIA rejected invalid GD&T creation 0x" & Hex(e) & " " & d
  Else
    ann.Name = "INVALID_GDT"
    changed = True
    WScript.Echo "[ATTEMPTED] INVALID_GDT created unexpected tolerance; reopen verifier must decide"
  End If
End Sub

Sub AttemptInvalidViewCapture()
  WScript.Echo "[BLOCKED] INVALID_VIEW_CAPTURE no reliable V5R21 Automation path found to save a broken Annotation View/Capture reference"
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

Function ObjectIsNothing(ByVal obj)
  ObjectIsNothing = True
  Err.Clear
  On Error Resume Next
  If Not obj Is Nothing Then ObjectIsNothing = False
  If Err.Number <> 0 Then ObjectIsNothing = True: Err.Clear
  On Error GoTo 0
End Function

Function ReopenHasAnnotationSet(ByVal path)
  Dim d, p
  ReopenHasAnnotationSet = False
  Err.Clear
  On Error Resume Next
  Set d = catia.Documents.Open(path)
  Set p = d.Part
  If Err.Number = 0 And Not p Is Nothing Then
    If p.AnnotationSets.Count > 0 Then ReopenHasAnnotationSet = True
  End If
  If Not d Is Nothing Then d.Close
  Err.Clear
  On Error GoTo 0
End Function

Sub EnsureFolder(ByVal path)
  If Len(path) = 0 Then Exit Sub
  If Not fso.FolderExists(path) Then fso.CreateFolder path
End Sub

Function CreateCatia()
  Err.Clear
  On Error Resume Next
  Set CreateCatia = CreateObject("CATIA.Application")
  Dim e, d: e = Err.Number: d = Err.Description
  On Error GoTo 0
  If e <> 0 Or CreateCatia Is Nothing Then WScript.Echo "[ERROR] Create CATIA.Application 0x" & Hex(e) & " " & d: WScript.Quit 9
End Function

Function TimestampText()
  Dim nowText
  nowText = CStr(Year(Now)) & Right("0" & Month(Now), 2) & Right("0" & Day(Now), 2) & "_" & Right("0" & Hour(Now), 2) & Right("0" & Minute(Now), 2) & Right("0" & Second(Now), 2)
  TimestampText = nowText
End Function

Function RuntimeText(): RuntimeText = "V" & cfg.Version & "R" & cfg.Release & "SP" & cfg.ServicePack: End Function
Sub Fatal(ByVal message, ByVal code)
  WScript.Echo "[ERROR] " & message
  On Error Resume Next
  If Not doc Is Nothing Then doc.Close
  If fso.FileExists(tmpPath) Then fso.DeleteFile tmpPath, True
  If Not catia Is Nothing Then catia.Quit
  WScript.Quit code
End Sub
