Option Explicit

' Adds one native FTA annotation by mode: roughness, flag, or noa.

Dim fso, fixtureDir, mode, path, catia, cfg, doc, part, annSet, annFactory, userSurfaces
Set fso = CreateObject("Scripting.FileSystemObject")
If WScript.Arguments.Count = 1 And LCase(WScript.Arguments(0)) = "--syntax-check" Then
  WScript.Echo "[SYNTAX-OK] add_one_supported_fta_annotation.vbs"
  WScript.Quit 0
End If
If WScript.Arguments.Count <> 2 Then WScript.Echo "Usage: cscript //nologo add_one_supported_fta_annotation.vbs <fixture-directory> <roughness|flag|noa>": WScript.Quit 2
fixtureDir = fso.GetAbsolutePathName(WScript.Arguments(0))
mode = LCase(WScript.Arguments(1))
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
Set annFactory = annSet.AnnotationFactory
Set userSurfaces = part.UserSurfaces

If mode = "roughness" Then AddRoughness
If mode = "flag" Then AddFlag
If mode = "noa" Then AddNoa
If mode <> "roughness" And mode <> "flag" And mode <> "noa" Then Fatal "Unknown mode " & mode, 5

doc.Close
catia.Quit
WScript.Quit 0

Sub AddRoughness()
  If HasAnnotation("ROUGHNESS_RA32") Then WScript.Echo "[SKIP] ROUGHNESS_RA32": Exit Sub
  Dim us, ann, rough, e, d
  Set us = TopUserSurface()
  Err.Clear
  On Error Resume Next
  Set ann = annFactory.CreateRoughness(us)
  e = Err.Number: d = Err.Description
  On Error GoTo 0
  If e <> 0 Or ann Is Nothing Then WScript.Echo "[COM-ERROR] ROUGHNESS_RA32 CreateRoughness 0x" & Hex(e) & " " & d: Exit Sub
  Err.Clear
  On Error Resume Next
  ann.Name = "ROUGHNESS_RA32"
  Set rough = ann.Roughness
  rough.SetField 1, "Ra 3.2"
  ann.ModifyVisu
  e = Err.Number: d = Err.Description
  On Error GoTo 0
  If e <> 0 Then WScript.Echo "[COM-ERROR] ROUGHNESS_RA32 set field/name 0x" & Hex(e) & " " & d: Exit Sub
  doc.Save
  WScript.Echo "[ADDED] ROUGHNESS_RA32 nativeType=" & AnnType(ann)
End Sub

Sub AddFlag()
  If HasAnnotation("FLAG_NOTE_1") Then WScript.Echo "[SKIP] FLAG_NOTE_1": Exit Sub
  Dim us, ann, e, d
  Set us = TopUserSurface()
  Err.Clear
  On Error Resume Next
  Set ann = annFactory.CreateFlagNote(us)
  e = Err.Number: d = Err.Description
  On Error GoTo 0
  If e <> 0 Or ann Is Nothing Then WScript.Echo "[COM-ERROR] FLAG_NOTE_1 CreateFlagNote 0x" & Hex(e) & " " & d: Exit Sub
  Err.Clear
  On Error Resume Next
  ann.Name = "FLAG_NOTE_1"
  ann.ModifyVisu
  e = Err.Number: d = Err.Description
  On Error GoTo 0
  If e <> 0 Then WScript.Echo "[COM-ERROR] FLAG_NOTE_1 set name 0x" & Hex(e) & " " & d: Exit Sub
  doc.Save
  WScript.Echo "[ADDED] FLAG_NOTE_1 nativeType=" & AnnType(ann)
End Sub

Sub AddNoa()
  If HasAnnotation("NOA_GENERAL_NOTE") Then WScript.Echo "[SKIP] NOA_GENERAL_NOTE": Exit Sub
  Dim us, noaObj, ann, e, d
  Set us = TopUserSurface()
  Err.Clear
  On Error Resume Next
  Set noaObj = annFactory.CreateTextNOA(us)
  noaObj.Text = "GENERAL NOTE"
  Set ann = annFactory.InstanciateNOA(noaObj, us)
  e = Err.Number: d = Err.Description
  On Error GoTo 0
  If e <> 0 Or ann Is Nothing Then WScript.Echo "[COM-ERROR] NOA_GENERAL_NOTE CreateTextNOA/InstanciateNOA 0x" & Hex(e) & " " & d: Exit Sub
  Err.Clear
  On Error Resume Next
  ann.Name = "NOA_GENERAL_NOTE"
  ann.ModifyVisu
  e = Err.Number: d = Err.Description
  On Error GoTo 0
  If e <> 0 Then WScript.Echo "[COM-ERROR] NOA_GENERAL_NOTE set name 0x" & Hex(e) & " " & d: Exit Sub
  doc.Save
  WScript.Echo "[ADDED] NOA_GENERAL_NOTE nativeType=" & AnnType(ann)
End Sub

Function TopUserSurface()
  Dim pad, ref
  Set pad = part.Bodies.Item(1).Shapes.Item("Pad_FTA_Carrier")
  Set ref = part.CreateReferenceFromBRepName("Face:(Brp:(Pad_FTA_Carrier;2);None:();Cf11:());WithTemporaryBody;WithoutBuildError;WithSelectingFeatureSupport;MFBRepVersion_CXR15)", pad)
  Set TopUserSurface = userSurfaces.Generate(ref)
End Function

Function HasAnnotation(ByVal objectName)
  Dim anns, i
  HasAnnotation = False
  Set anns = annSet.Annotations
  For i = 1 To anns.Count
    If LCase(SafeName(anns.Item(i))) = LCase(objectName) Then HasAnnotation = True: Exit Function
  Next
End Function

Function SafeName(ByVal obj)
  SafeName = ""
  Err.Clear
  On Error Resume Next
  SafeName = CStr(obj.Name)
  If Err.Number <> 0 Then SafeName = "": Err.Clear
  On Error GoTo 0
End Function

Function AnnType(ByVal ann)
  AnnType = TypeName(ann)
  Err.Clear
  On Error Resume Next
  AnnType = AnnType & "/Type=" & ann.Type & "/SuperType=" & ann.SuperType
  If Err.Number <> 0 Then Err.Clear
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
