Option Explicit

' Renames the first real native FTA text annotation in fta_all_semantic_types.CATPart.
' This edits an existing Annotation object only; it does not create placeholders.

Dim fso, fixtureDir, path, catia, cfg, doc, part, sets, setObj, annotations, annot, txt
Set fso = CreateObject("Scripting.FileSystemObject")
If WScript.Arguments.Count = 1 And LCase(WScript.Arguments(0)) = "--syntax-check" Then
  WScript.Echo "[SYNTAX-OK] rename_first_fta_text_note.vbs"
  WScript.Quit 0
End If
If WScript.Arguments.Count <> 1 Then
  WScript.Echo "Usage: cscript //nologo rename_first_fta_text_note.vbs <fixture-directory>"
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
Set annotations = setObj.Annotations
If annotations.Count < 1 Then Fatal "Annotation count is zero", 6
Set annot = annotations.Item(1)

Err.Clear
On Error Resume Next
annot.Name = "TEXT_PROCESS_NOTE"
Set txt = annot.Text
txt.Text = "REMOVE BURRS"
annot.ModifyVisu
Dim e, d: e = Err.Number: d = Err.Description
On Error GoTo 0
If e <> 0 Then Fatal "Rename/set text failed 0x" & Hex(e) & " " & d, 7

doc.Save
doc.Close
catia.Quit
WScript.Echo "[RENAMED] TEXT_PROCESS_NOTE saved in " & path
WScript.Quit 0

Function OpenDocument(ByVal p)
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
