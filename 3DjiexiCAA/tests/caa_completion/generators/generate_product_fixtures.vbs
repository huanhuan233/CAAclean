Option Explicit

' Generates CATProduct fixtures with real external CATPart references and instance transforms.
' Unsupported Assembly Automation is logged as BLOCKED; no empty CATProduct is accepted.

Dim fso, fixtureDir, ledger, catia, cfg, partPath
Set fso = CreateObject("Scripting.FileSystemObject")
If WScript.Arguments.Count <> 1 Then
  WScript.Echo "Usage: cscript //nologo generate_product_fixtures.vbs <fixture-directory>"
  WScript.Quit 2
End If
fixtureDir = fso.GetAbsolutePathName(WScript.Arguments(0))
partPath = fso.BuildPath(fixtureDir, "pd_pad_primitives.CATPart")
If Not fso.FileExists(partPath) Then
  WScript.Echo "[ERROR] Missing prerequisite " & partPath
  WScript.Quit 3
End If
Set ledger = fso.OpenTextFile(fso.BuildPath(fixtureDir, "generation_ledger.tsv"), 8, True, 0)

On Error Resume Next
Set catia = CreateObject("CATIA.Application")
If Err.Number <> 0 Then Fatal "Create CATIA.Application", 4
catia.Visible = False: catia.DisplayFileAlerts = False
Set cfg = catia.SystemConfiguration
If Err.Number <> 0 Or cfg.Version <> 5 Or cfg.Release <> 21 Then Fatal "Expected CATIA V5R21", 5

BuildSameReferenceProduct
BuildNestedProduct
BuildProductVersionPair

ledger.Close: catia.Quit
WScript.Echo "[DONE] CATProduct probes completed"
WScript.Quit 0

Sub BuildSameReferenceProduct()
  On Error Resume Next
  Dim path, doc, root, products, files(0), c1, c2, matrix(11), e, d
  path = fso.BuildPath(fixtureDir, "product_same_reference_instances.CATProduct")
  If fso.FileExists(path) Then fso.DeleteFile path, True
  Err.Clear
  Set doc = catia.Documents.Add("Product")
  Set root = doc.Product: root.PartNumber = "CAA_PRODUCT_MULTI_INSTANCE"
  Set products = root.Products
  files(0) = partPath
  products.AddComponentsFromFiles files, "All"
  products.AddComponentsFromFiles files, "All"
  Set c1 = products.Item(1): c1.Name = "PadReference_Instance_A"
  Set c2 = products.Item(2): c2.Name = "PadReference_Instance_B"
  IdentityMatrix matrix
  matrix(9) = 140: matrix(10) = 20: matrix(11) = 0
  c2.Move.Apply matrix
  root.Update
  If products.Count <> 2 Then Err.Raise 9101, , "Expected two product instances"
  doc.SaveAs path
  e = Err.Number: d = Err.Description: Err.Clear
  doc.Close
  ReportProduct path, e, d, "same reference; two instances; transform"
End Sub

Sub BuildNestedProduct()
  On Error Resume Next
  Dim path, doc, root, subA, subB, files(0), matrix(11), e, d
  path = fso.BuildPath(fixtureDir, "product_nested.CATProduct")
  If fso.FileExists(path) Then fso.DeleteFile path, True
  Err.Clear
  Set doc = catia.Documents.Add("Product")
  Set root = doc.Product: root.PartNumber = "CAA_PRODUCT_NESTED"
  Set subA = root.Products.AddNewProduct("SUBASSEMBLY_A")
  files(0) = partPath: subA.Products.AddComponentsFromFiles files, "All"
  Set subB = subA.Products.AddNewProduct("SUBASSEMBLY_B")
  subB.Products.AddComponentsFromFiles files, "All"
  IdentityMatrix matrix: matrix(11) = 80: subB.Move.Apply matrix
  root.Update
  doc.SaveAs path
  e = Err.Number: d = Err.Description: Err.Clear
  doc.Close
  ReportProduct path, e, d, "three-level nesting"
End Sub

Sub BuildProductVersionPair()
  On Error Resume Next
  Dim v1, v2, doc, root, products, files(0), matrix(11), e, d
  v1 = fso.BuildPath(fixtureDir, "version_product_v1.CATProduct")
  v2 = fso.BuildPath(fixtureDir, "version_product_v2.CATProduct")
  If fso.FileExists(v1) Then fso.DeleteFile v1, True
  If fso.FileExists(v2) Then fso.DeleteFile v2, True
  Err.Clear
  Set doc = catia.Documents.Add("Product")
  Set root = doc.Product: root.PartNumber = "CAA_PRODUCT_VERSION": Set products = root.Products
  files(0) = partPath: products.AddComponentsFromFiles files, "All": root.Update: doc.SaveAs v1
  products.AddComponentsFromFiles files, "All"
  products.Item(2).Name = "AddedInV2"
  IdentityMatrix matrix: matrix(9) = 90: matrix(11) = 15: products.Item(2).Move.Apply matrix
  root.Revision = "B": root.Update: doc.SaveAs v2
  e = Err.Number: d = Err.Description: Err.Clear
  doc.Close
  If e <> 0 Then
    If fso.FileExists(v1) Then fso.DeleteFile v1, True
    If fso.FileExists(v2) Then fso.DeleteFile v2, True
    ledger.WriteLine "version_product_v1.CATProduct|version_product_v2.CATProduct" & vbTab & "blocked" & vbTab & RuntimeText() & vbTab & "0x" & Hex(e) & " " & Clean(d)
  Else
    ledger.WriteLine "version_product_v1.CATProduct|version_product_v2.CATProduct" & vbTab & "generated" & vbTab & RuntimeText() & vbTab & "real BOM and transform pair"
  End If
End Sub

Sub ReportProduct(ByVal path, ByVal errNo, ByVal errText, ByVal evidence)
  On Error Resume Next
  If errNo <> 0 Then
    If fso.FileExists(path) Then fso.DeleteFile path, True
    ledger.WriteLine fso.GetFileName(path) & vbTab & "blocked" & vbTab & RuntimeText() & vbTab & "0x" & Hex(errNo) & " " & Clean(errText)
    WScript.Echo "[BLOCKED] " & fso.GetFileName(path)
  Else
    ledger.WriteLine fso.GetFileName(path) & vbTab & "generated" & vbTab & RuntimeText() & vbTab & evidence
    WScript.Echo "[GENERATED] " & fso.GetFileName(path)
  End If
End Sub

Sub IdentityMatrix(ByRef m)
  m(0)=1: m(1)=0: m(2)=0: m(3)=0: m(4)=1: m(5)=0
  m(6)=0: m(7)=0: m(8)=1: m(9)=0: m(10)=0: m(11)=0
End Sub

Function RuntimeText(): RuntimeText = "V" & cfg.Version & "R" & cfg.Release & "SP" & cfg.ServicePack: End Function
Function Clean(ByVal v): Clean = Replace(Replace(CStr(v), vbTab, " "), vbCrLf, " "): End Function
Sub Fatal(ByVal message, ByVal code)
  On Error Resume Next
  WScript.Echo "[ERROR] " & message & " 0x" & Hex(Err.Number) & " " & Err.Description
  ledger.Close: If Not catia Is Nothing Then catia.Quit
  WScript.Quit code
End Sub

