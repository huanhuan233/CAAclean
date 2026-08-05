Option Explicit

' Safely performs the CATIA SaveAs step from an FTA scaffold to the formal FTA file.
' It never overwrites an existing formal file. On success, the formal file is left open
' in visible CATIA so manual FTA/MBD annotation work can continue.

Dim fso, fixtureDir, baseName, scaffoldPath, formalPath, catia, cfg, doc
Set fso = CreateObject("Scripting.FileSystemObject")

If WScript.Arguments.Count = 1 And LCase(WScript.Arguments(0)) = "--syntax-check" Then
  WScript.Echo "[SYNTAX-OK] save_fta_formal_from_scaffold.vbs"
  WScript.Quit 0
End If
If WScript.Arguments.Count <> 2 Then
  WScript.Echo "Usage: cscript //nologo save_fta_formal_from_scaffold.vbs <fixture-directory> <base-name>"
  WScript.Quit 2
End If

fixtureDir = fso.GetAbsolutePathName(WScript.Arguments(0))
baseName = WScript.Arguments(1)
scaffoldPath = fso.BuildPath(fixtureDir, baseName & "_scaffold.CATPart")
formalPath = fso.BuildPath(fixtureDir, baseName & ".CATPart")

If Not fso.FileExists(scaffoldPath) Then
  WScript.Echo "[ERROR] Missing scaffold " & scaffoldPath
  WScript.Quit 3
End If
If fso.FileExists(formalPath) Then
  WScript.Echo "[PRESERVE] Formal FTA already exists; not overwritten: " & formalPath
  WScript.Quit 0
End If

Set catia = CreateCatia()
catia.Visible = True
catia.DisplayFileAlerts = False
Set cfg = catia.SystemConfiguration
If cfg.Version <> 5 Or cfg.Release <> 21 Then Fatal "Expected CATIA V5R21, got " & RuntimeText(), 4
WScript.Echo "[CATIA] " & RuntimeText()

Set doc = OpenDocument(scaffoldPath)
Err.Clear
On Error Resume Next
doc.SaveAs formalPath
Dim e, d: e = Err.Number: d = Err.Description
On Error GoTo 0
If e <> 0 Then Fatal "SaveAs formal FTA failed 0x" & Hex(e) & " " & d, 5

WScript.Echo "[SAVED-AS] " & formalPath
WScript.Echo "[OPEN] Formal FTA file is left open in CATIA for manual native FTA annotation work"
WScript.Quit 0

Function OpenDocument(ByVal path)
  Err.Clear
  On Error Resume Next
  Set OpenDocument = catia.Documents.Open(path)
  Dim e, d: e = Err.Number: d = Err.Description
  On Error GoTo 0
  If e <> 0 Or OpenDocument Is Nothing Then Fatal "Open scaffold failed 0x" & Hex(e) & " " & d, 6
End Function

Function CreateCatia()
  Err.Clear
  On Error Resume Next
  Set CreateCatia = CreateObject("CATIA.Application")
  Dim e, d: e = Err.Number: d = Err.Description
  On Error GoTo 0
  If e <> 0 Or CreateCatia Is Nothing Then
    WScript.Echo "[ERROR] Create CATIA.Application 0x" & Hex(e) & " " & d
    WScript.Quit 7
  End If
End Function

Function RuntimeText(): RuntimeText = "V" & cfg.Version & "R" & cfg.Release & "SP" & cfg.ServicePack: End Function
Sub Fatal(ByVal message, ByVal code)
  WScript.Echo "[ERROR] " & message
  WScript.Quit code
End Sub
