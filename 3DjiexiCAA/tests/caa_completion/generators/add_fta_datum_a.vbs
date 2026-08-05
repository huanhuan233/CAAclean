Option Explicit

' Adds a real native FTA datum annotation DATUM_A to fta_all_semantic_types.CATPart.

Dim fso, fixtureDir, path, catia, cfg, doc, part, sets, setObj, annFactory
Dim pad, faceRef, userSurface, datumAnn, datumSimple
Set fso = CreateObject("Scripting.FileSystemObject")
If WScript.Arguments.Count = 1 And LCase(WScript.Arguments(0)) = "--syntax-check" Then
  WScript.Echo "[SYNTAX-OK] add_fta_datum_a.vbs"
  WScript.Quit 0
End If
If WScript.Arguments.Count <> 1 Then
  WScript.Echo "Usage: cscript //nologo add_fta_datum_a.vbs <fixture-directory>"
  WScript.Quit 2
End If

fixtureDir = fso.GetAbsolutePathName(WScript.Arguments(0))
path = fso.BuildPath(fixtureDir, "fta_all_semantic_types.CATPart")
If Not fso.FileExists(path) Then
  WScript.Echo "[ERROR] Missing formal FTA file " & path
  WScript.Quit 3
End If

Set catia = CreateCatia()
catia.Visible = True
catia.DisplayFileAlerts = False
Set cfg = catia.SystemConfiguration
If cfg.Version <> 5 Or cfg.Release <> 21 Then Fatal "Expected CATIA V5R21, got " & RuntimeText(), 4

Set doc = OpenDocument(path)
Set part = doc.Part
Set sets = part.AnnotationSets
If sets.Count < 1 Then Fatal "AnnotationSets.Count=0", 5
Set setObj = sets.Item(1)
Set annFactory = setObj.AnnotationFactory
Set pad = part.Bodies.Item(1).Shapes.Item("Pad_FTA_Carrier")
Set faceRef = part.CreateReferenceFromBRepName("Face:(Brp:(Pad_FTA_Carrier;2);None:();Cf11:());WithTemporaryBody;WithoutBuildError;WithSelectingFeatureSupport;MFBRepVersion_CXR15)", pad)
Set userSurface = part.UserSurfaces.Generate(faceRef)

Err.Clear
On Error Resume Next
Set datumAnn = annFactory.CreateEvoluateDatum(userSurface, 5, 5, 35, True)
Dim e, d: e = Err.Number: d = Err.Description
On Error GoTo 0
If e <> 0 Or datumAnn Is Nothing Then Fatal "CreateEvoluateDatum failed 0x" & Hex(e) & " " & d, 6

Err.Clear
On Error Resume Next
datumAnn.Name = "DATUM_A"
Set datumSimple = datumAnn.DatumSimple
datumSimple.Label = "A"
datumAnn.ModifyVisu
e = Err.Number: d = Err.Description
On Error GoTo 0
If e <> 0 Then Fatal "Set DATUM_A name/label failed 0x" & Hex(e) & " " & d, 7

doc.Save
doc.Close
catia.Quit
WScript.Echo "[ADDED] DATUM_A saved in " & path
WScript.Quit 0

Function OpenDocument(ByVal p)
  Dim i, existing
  Err.Clear
  On Error Resume Next
  For i = 1 To catia.Documents.Count
    Set existing = catia.Documents.Item(i)
    If LCase(CStr(existing.FullName)) = LCase(CStr(p)) Then
      Set OpenDocument = existing
      Err.Clear
      On Error GoTo 0
      WScript.Echo "[REUSE-OPEN] " & p
      Exit Function
    End If
    Err.Clear
  Next
  On Error GoTo 0
  Err.Clear
  On Error Resume Next
  Set OpenDocument = catia.Documents.Open(p)
  Dim e, d: e = Err.Number: d = Err.Description
  On Error GoTo 0
  If e <> 0 Or OpenDocument Is Nothing Then Fatal "Open failed 0x" & Hex(e) & " " & d, 8
End Function

Function CreateCatia()
  Err.Clear
  On Error Resume Next
  Set CreateCatia = CreateObject("CATIA.Application")
  Dim e, d: e = Err.Number: d = Err.Description
  On Error GoTo 0
  If e <> 0 Or CreateCatia Is Nothing Then
    WScript.Echo "[ERROR] Create CATIA.Application 0x" & Hex(e) & " " & d
    WScript.Quit 9
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
