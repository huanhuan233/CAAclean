Option Explicit

' Read-only native FTA acceptance verifier. It never updates or saves CATIA documents.
' Scaffolds are reported as evidence but cannot satisfy formal FTA fixture requirements.

Dim fso, fixtureDir, reportPath, report, ledger, catia, cfg, failures
Set fso = CreateObject("Scripting.FileSystemObject")
If WScript.Arguments.Count = 1 And LCase(WScript.Arguments(0)) = "--syntax-check" Then
  WScript.Echo "[SYNTAX-OK] verify_native_fta_fixtures.vbs"
  WScript.Quit 0
End If
If WScript.Arguments.Count <> 1 Then
  WScript.Echo "Usage: cscript //nologo verify_native_fta_fixtures.vbs <fixture-directory>"
  WScript.Quit 2
End If

fixtureDir = fso.GetAbsolutePathName(WScript.Arguments(0))
reportPath = fso.BuildPath(fixtureDir, "fta_fixture_evidence.jsonl")
Set report = fso.CreateTextFile(reportPath, True, False)
Set ledger = fso.OpenTextFile(fso.BuildPath(fixtureDir, "generation_ledger.tsv"), 8, True, 0)
failures = 0

Set catia = CreateCatia()
catia.Visible = False
catia.DisplayFileAlerts = False
Set cfg = catia.SystemConfiguration
If cfg.Version <> 5 Or cfg.Release <> 21 Then Fatal "Expected CATIA V5R21, got " & RuntimeText(), 4
WScript.Echo "[CATIA] " & RuntimeText()

VerifyOne "fta_all_semantic_types.CATPart", "DIM_LINEAR_FACE_FACE|DIM_DIAMETER_CYLINDER|DIM_LIMIT_DEVIATION|GDT_POSITION_DRF_ABC|GDT_FLATNESS|DATUM_A|DATUM_B|DATUM_C|ROUGHNESS_RA32|TEXT_PROCESS_NOTE|FLAG_NOTE_1|NOA_GENERAL_NOTE|VIEW_FRONT|VIEW_TOP|CAPTURE_MACHINING", "semantic_all"
VerifyOne "fta_geometry_references.CATPart", "REF_FACE|REF_EDGE|REF_VERTEX|REF_AXIS|REF_DATUM_PLANE|REF_TTRS_MULTI", "geometry_references"
VerifyOne "fta_orphan_invalid.CATPart", "ORPHAN_DELETED_FACE|ORPHAN_SUPPRESSED_FEATURE|INVALID_GDT|INVALID_VIEW_CAPTURE", "orphan_invalid"
VerifyOne "version_fta_v1.CATPart", "DIM_LINEAR_FACE_FACE|DIM_DIAMETER_CYLINDER|DIM_LIMIT_DEVIATION|GDT_POSITION_DRF_ABC|GDT_FLATNESS|DATUM_A|DATUM_B|DATUM_C|ROUGHNESS_RA32|TEXT_PROCESS_NOTE|FLAG_NOTE_1|NOA_GENERAL_NOTE|VIEW_FRONT|VIEW_TOP|CAPTURE_MACHINING", "version_v1"
VerifyOne "version_fta_v2.CATPart", "DIM_LINEAR_FACE_FACE|DIM_DIAMETER_CYLINDER|DIM_LIMIT_DEVIATION|GDT_POSITION_DRF_ABC|GDT_FLATNESS|DATUM_A|DATUM_B|DATUM_C|ROUGHNESS_RA32|TEXT_PROCESS_NOTE|FLAG_NOTE_1|NOA_GENERAL_NOTE|VIEW_FRONT|VIEW_TOP|CAPTURE_MACHINING", "version_v2"

VerifyVersionDelta

report.Close
ledger.Close
catia.Quit
If failures > 0 Then
  WScript.Echo "[FAIL] native FTA verification failures=" & failures & " evidence=" & reportPath
  WScript.Quit 1
End If
WScript.Echo "[PASS] native FTA fixtures verified; evidence=" & reportPath
WScript.Quit 0

Sub VerifyOne(ByVal fileName, ByVal expectedNamesText, ByVal profile)
  Dim path, scaffoldPath, doc, part, annotationSetCount, annotationCount, viewCount, captureCount
  Dim annotationsJson, foundNames, missingNames, geomJson, status, reason, ok
  path = fso.BuildPath(fixtureDir, fileName)
  scaffoldPath = fso.BuildPath(fixtureDir, Replace(fileName, ".CATPart", "_scaffold.CATPart"))
  status = "blocked": reason = "": ok = False
  annotationSetCount = 0: annotationCount = 0: viewCount = 0: captureCount = 0
  annotationsJson = "[]": geomJson = "{}": foundNames = "|"

  If Not fso.FileExists(path) Then
    reason = "formal CATPart missing"
    If fso.FileExists(scaffoldPath) Then reason = reason & "; scaffold exists but cannot substitute formal native FTA"
    failures = failures + 1
    WriteEvidence fileName, status, reason, annotationSetCount, annotationCount, annotationsJson, viewCount, captureCount, geomJson
    ledger.WriteLine fileName & vbTab & "blocked" & vbTab & RuntimeText() & vbTab & reason
    WScript.Echo "[BLOCKED] " & fileName & " " & reason
    Exit Sub
  End If

  Err.Clear
  On Error Resume Next
  Set doc = catia.Documents.Open(path)
  Dim e, d: e = Err.Number: d = Err.Description
  On Error GoTo 0
  If e <> 0 Or doc Is Nothing Then
    reason = "open failed 0x" & Hex(e) & " " & d
    failures = failures + 1
    WriteEvidence fileName, status, reason, annotationSetCount, annotationCount, annotationsJson, viewCount, captureCount, geomJson
    ledger.WriteLine fileName & vbTab & "blocked" & vbTab & RuntimeText() & vbTab & reason
    WScript.Echo "[BLOCKED] " & fileName & " " & reason
    Exit Sub
  End If

  Set part = doc.Part
  annotationSetCount = CountProperty(part, "AnnotationSets")
  annotationsJson = CollectAnnotations(part, annotationCount, foundNames)
  CollectViewAndCaptureNames part, foundNames
  viewCount = CountNestedByNames(part, "TPSViews|AnnotationViews|Views")
  captureCount = CountNestedByNames(part, "Captures|TPSCaptures")
  geomJson = GeometryStatus(profile, foundNames, annotationCount)
  doc.Close

  missingNames = MissingExpected(expectedNamesText, foundNames)
  If annotationSetCount <= 0 Then
    reason = "AnnotationSets.Count=0"
  ElseIf annotationCount <= 0 Then
    reason = "native annotation/TPS object count is zero"
  ElseIf Len(missingNames) > 0 Then
    reason = "missing fixed native FTA names: " & missingNames
  ElseIf profile = "semantic_all" And (viewCount < 2 Or captureCount < 1) Then
    reason = "required Annotation View/Capture not found: views=" & viewCount & " captures=" & captureCount
  ElseIf profile = "geometry_references" And Not GeometryCoverageOk(foundNames) Then
    reason = "geometry reference coverage incomplete"
  ElseIf profile = "orphan_invalid" Then
    reason = "orphan/invalid native FTA scenario was not proven by fixed broken-reference names"
  Else
    status = "verified": reason = "native FTA reopened and fixed names present": ok = True
  End If

  If Not ok Then failures = failures + 1
  WriteEvidence fileName, status, reason, annotationSetCount, annotationCount, annotationsJson, viewCount, captureCount, geomJson
  ledger.WriteLine fileName & vbTab & status & vbTab & RuntimeText() & vbTab & reason
  WScript.Echo "[" & UCase(status) & "] " & fileName & " annotations=" & annotationCount & " views=" & viewCount & " captures=" & captureCount & " " & reason
End Sub

Function CollectAnnotations(ByVal part, ByRef total, ByRef foundNames)
  Dim sets, setObj, annotations, item, i, j, text, itemName, itemType
  total = 0: foundNames = "|": text = "["
  Err.Clear
  On Error Resume Next
  Set sets = part.AnnotationSets
  If Err.Number <> 0 Or sets Is Nothing Then Err.Clear: On Error GoTo 0: CollectAnnotations = "[]": Exit Function
  For i = 1 To sets.Count
    Set setObj = sets.Item(i)
    Err.Clear
    Set annotations = setObj.Annotations
    If Err.Number = 0 And Not annotations Is Nothing Then
      For j = 1 To annotations.Count
        Set item = annotations.Item(j)
        itemName = SafeName(item)
        itemType = TypeName(item)
        If total > 0 Then text = text & ","
        text = text & "{""set"":""" & JsonText(SafeName(setObj)) & """,""name"":""" & JsonText(itemName) & """,""automation_type"":""" & JsonText(itemType) & """}"
        foundNames = foundNames & itemName & "|"
        total = total + 1
      Next
    End If
    Err.Clear
  Next
  On Error GoTo 0
  CollectAnnotations = text & "]"
End Function

Sub CollectViewAndCaptureNames(ByVal part, ByRef foundNames)
  Dim sets, setObj, coll, item, i, j
  Err.Clear
  On Error Resume Next
  Set sets = part.AnnotationSets
  If Err.Number <> 0 Or sets Is Nothing Then Err.Clear: On Error GoTo 0: Exit Sub
  For i = 1 To sets.Count
    Set setObj = sets.Item(i)
    Set coll = Nothing
    Err.Clear
    Set coll = setObj.TPSViews
    If Err.Number = 0 And Not coll Is Nothing Then
      For j = 1 To coll.Count
        Set item = coll.Item(j)
        foundNames = foundNames & SafeName(item) & "|"
      Next
    End If
    Err.Clear
    Set coll = setObj.Captures
    If Err.Number = 0 And Not coll Is Nothing Then
      For j = 1 To coll.Count
        Set item = coll.Item(j)
        foundNames = foundNames & SafeName(item) & "|"
      Next
    End If
    Err.Clear
  Next
  On Error GoTo 0
End Sub

Function CountNestedByNames(ByVal part, ByVal namesText)
  Dim sets, setObj, names, idx, coll, i, count
  CountNestedByNames = 0: count = 0
  Err.Clear
  On Error Resume Next
  Set sets = part.AnnotationSets
  If Err.Number <> 0 Or sets Is Nothing Then Err.Clear: On Error GoTo 0: Exit Function
  names = Split(namesText, "|")
  For i = 1 To sets.Count
    Set setObj = sets.Item(i)
    For idx = 0 To UBound(names)
      Set coll = Nothing
      Err.Clear
      Execute "Set coll = setObj." & names(idx)
      If Err.Number = 0 And Not coll Is Nothing Then count = count + coll.Count
      Err.Clear
    Next
  Next
  On Error GoTo 0
  CountNestedByNames = count
End Function

Function CountProperty(ByVal obj, ByVal propName)
  Dim coll
  CountProperty = 0
  Err.Clear
  On Error Resume Next
  Execute "Set coll = obj." & propName
  If Err.Number = 0 And Not coll Is Nothing Then CountProperty = coll.Count
  Err.Clear
  On Error GoTo 0
End Function

Function GeometryStatus(ByVal profile, ByVal foundNames, ByVal annotationCount)
  GeometryStatus = "{""status"":""" & JsonText(profile) & """,""annotation_count"":" & annotationCount & ",""face"":" & BoolText(InNames(foundNames, "REF_FACE")) & ",""edge"":" & BoolText(InNames(foundNames, "REF_EDGE")) & ",""vertex"":" & BoolText(InNames(foundNames, "REF_VERTEX")) & ",""axis"":" & BoolText(InNames(foundNames, "REF_AXIS")) & ",""datum_plane"":" & BoolText(InNames(foundNames, "REF_DATUM_PLANE")) & ",""multi_geometry"":" & BoolText(InNames(foundNames, "REF_TTRS_MULTI")) & "}"
End Function

Function GeometryCoverageOk(ByVal foundNames)
  GeometryCoverageOk = InNames(foundNames, "REF_FACE") And InNames(foundNames, "REF_EDGE") And InNames(foundNames, "REF_VERTEX") And InNames(foundNames, "REF_AXIS") And InNames(foundNames, "REF_DATUM_PLANE") And InNames(foundNames, "REF_TTRS_MULTI")
End Function

Sub VerifyVersionDelta()
  Dim v1, v2
  v1 = fso.BuildPath(fixtureDir, "version_fta_v1.CATPart")
  v2 = fso.BuildPath(fixtureDir, "version_fta_v2.CATPart")
  If Not fso.FileExists(v1) Or Not fso.FileExists(v2) Then
    report.WriteLine "{""file"":""version_fta_v1.CATPart|version_fta_v2.CATPart"",""reopen_status"":""blocked"",""blocked_reason"":""version pair missing; cannot compare native FTA semantic delta""}"
    Exit Sub
  End If
  report.WriteLine "{""file"":""version_fta_v1.CATPart|version_fta_v2.CATPart"",""reopen_status"":""needs_caa_semantic_compare"",""blocked_reason"":""native pair exists; detailed semantic value/reference delta must be confirmed by fixed-name TPS payload extraction""}"
End Sub

Function MissingExpected(ByVal expectedNamesText, ByVal foundNames)
  Dim arr, i, missing
  MissingExpected = ""
  If Len(expectedNamesText) = 0 Then Exit Function
  arr = Split(expectedNamesText, "|")
  missing = ""
  For i = 0 To UBound(arr)
    If Len(arr(i)) > 0 And Not InNames(foundNames, arr(i)) Then
      If Len(missing) > 0 Then missing = missing & ","
      missing = missing & arr(i)
    End If
  Next
  MissingExpected = missing
End Function

Function InNames(ByVal namesText, ByVal name)
  InNames = (InStr(1, namesText, "|" & name & "|", vbTextCompare) > 0)
End Function

Function SafeName(ByVal obj)
  SafeName = ""
  Err.Clear
  On Error Resume Next
  SafeName = CStr(obj.Name)
  If Err.Number <> 0 Then SafeName = "": Err.Clear
  On Error GoTo 0
End Function

Sub WriteEvidence(ByVal fileName, ByVal status, ByVal reason, ByVal annotationSetCount, ByVal annotationCount, ByVal annotationsJson, ByVal viewCount, ByVal captureCount, ByVal geomJson)
  report.WriteLine "{""file"":""" & JsonText(fileName) & """,""reopen_status"":""" & JsonText(status) & """,""annotation_set_count"":" & annotationSetCount & ",""annotation_count"":" & annotationCount & ",""annotations"":" & annotationsJson & ",""view_count"":" & viewCount & ",""capture_count"":" & captureCount & ",""geometry_reference_status"":" & geomJson & ",""blocked_reason"":""" & JsonText(reason) & """}"
End Sub

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

Function JsonText(ByVal value)
  Dim text: text = CStr(value)
  text = Replace(text, Chr(92), Chr(92) & Chr(92))
  text = Replace(text, Chr(34), Chr(92) & Chr(34))
  text = Replace(text, vbCr, Chr(92) & "r")
  text = Replace(text, vbLf, Chr(92) & "n")
  JsonText = text
End Function

Function BoolText(ByVal value): If value Then BoolText = "true" Else BoolText = "false": End If: End Function
Function RuntimeText(): RuntimeText = "V" & cfg.Version & "R" & cfg.Release & "SP" & cfg.ServicePack: End Function

Sub Fatal(ByVal message, ByVal code)
  WScript.Echo "[ERROR] " & message
  On Error Resume Next
  If Not report Is Nothing Then report.Close
  If Not ledger Is Nothing Then ledger.Close
  If Not catia Is Nothing Then catia.Quit
  WScript.Quit code
End Sub
