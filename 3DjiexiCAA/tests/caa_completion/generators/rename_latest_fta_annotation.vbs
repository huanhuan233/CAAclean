Option Explicit

' Renames the latest real native FTA annotation that does not already use one of the
' fixed fixture names. This is used after a manual GUI-created native annotation.

Dim fso, fixtureDir, targetName, path, catia, cfg, doc, part, annSet, anns, i, ann
Set fso = CreateObject("Scripting.FileSystemObject")
If WScript.Arguments.Count = 1 And LCase(WScript.Arguments(0)) = "--syntax-check" Then
  WScript.Echo "[SYNTAX-OK] rename_latest_fta_annotation.vbs"
  WScript.Quit 0
End If
If WScript.Arguments.Count <> 2 Then
  WScript.Echo "Usage: cscript //nologo rename_latest_fta_annotation.vbs <fixture-directory> <target-name>"
  WScript.Quit 2
End If

fixtureDir = fso.GetAbsolutePathName(WScript.Arguments(0))
targetName = WScript.Arguments(1)
path = fso.BuildPath(fixtureDir, "fta_all_semantic_types.CATPart")
If Not fso.FileExists(path) Then WScript.Echo "[ERROR] Missing " & path: WScript.Quit 3

Set catia = CreateCatia()
catia.Visible = True
catia.DisplayFileAlerts = False
Set cfg = catia.SystemConfiguration
If cfg.Version <> 5 Or cfg.Release <> 21 Then Fatal "Expected CATIA V5R21, got " & RuntimeText(), 4
Set doc = catia.Documents.Open(path)
Set part = doc.Part
Set annSet = part.AnnotationSets.Item(1)
Set anns = annSet.Annotations

Set ann = Nothing
For i = anns.Count To 1 Step -1
  If Not IsFixedName(SafeName(anns.Item(i))) Then
    Set ann = anns.Item(i)
    Exit For
  End If
Next
If ann Is Nothing Then Fatal "No non-fixed native FTA annotation found to rename", 5

Dim oldName, e, d
oldName = SafeName(ann)
Err.Clear
On Error Resume Next
ann.Name = targetName
ann.ModifyVisu
e = Err.Number: d = Err.Description
On Error GoTo 0
If e <> 0 Then Fatal "Rename annotation failed 0x" & Hex(e) & " " & d, 6

doc.Save
doc.Close
catia.Quit
WScript.Echo "[RENAMED] " & oldName & " -> " & targetName
WScript.Quit 0

Function IsFixedName(ByVal name)
  Dim fixed
  fixed = "|TEXT_PROCESS_NOTE|DATUM_A|DATUM_B|DATUM_C|GDT_FLATNESS|ROUGHNESS_RA32|FLAG_NOTE_1|DIM_LINEAR_FACE_FACE|DIM_DIAMETER_CYLINDER|DIM_LIMIT_DEVIATION|GDT_POSITION_DRF_ABC|NOA_GENERAL_NOTE|"
  IsFixedName = (InStr(1, fixed, "|" & name & "|", vbTextCompare) > 0)
End Function

Function SafeName(ByVal obj)
  SafeName = ""
  Err.Clear
  On Error Resume Next
  SafeName = CStr(obj.Name)
  If Err.Number <> 0 Then SafeName = "": Err.Clear
  On Error GoTo 0
End Function

Function CreateCatia()
  Err.Clear
  On Error Resume Next
  Set CreateCatia = CreateObject("CATIA.Application")
  Dim e, d: e = Err.Number: d = Err.Description
  On Error GoTo 0
  If e <> 0 Or CreateCatia Is Nothing Then WScript.Echo "[ERROR] Create CATIA.Application 0x" & Hex(e) & " " & d: WScript.Quit 9
End Function

Function RuntimeText(): RuntimeText = "V" & cfg.Version & "R" & cfg.Release & "SP" & cfg.ServicePack: End Function
Sub Fatal(ByVal message, ByVal code)
  WScript.Echo "[ERROR] " & message
  On Error Resume Next
  If Not doc Is Nothing Then doc.Close
  If Not catia Is Nothing Then catia.Quit
  WScript.Quit code
End Sub
