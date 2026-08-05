Option Explicit

' Generates CATProduct fixtures with real external CATPart references and instance transforms.
' Every product is first saved to a temporary file, closed, reopened, verified, then promoted.

Dim fso, fixtureDir, ledger, catia, cfg, partPath, backupDir
Set fso = CreateObject("Scripting.FileSystemObject")
If WScript.Arguments.Count = 1 And LCase(WScript.Arguments(0)) = "--syntax-check" Then
  WScript.Echo "[SYNTAX-OK] generate_product_fixtures.vbs"
  WScript.Quit 0
End If
If WScript.Arguments.Count <> 1 Then
  WScript.Echo "Usage: cscript //nologo generate_product_fixtures.vbs <fixture-directory>"
  WScript.Quit 2
End If

fixtureDir = fso.GetAbsolutePathName(WScript.Arguments(0))
partPath = fso.BuildPath(fixtureDir, "pd_pad_primitives.CATPart")
backupDir = fso.BuildPath(fixtureDir, "product_fta_backups")
If Not fso.FolderExists(fixtureDir) Then fso.CreateFolder fixtureDir
If Not fso.FolderExists(backupDir) Then fso.CreateFolder backupDir
If Not fso.FileExists(partPath) Then
  WScript.Echo "[ERROR] Missing prerequisite " & partPath
  WScript.Quit 3
End If
Set ledger = fso.OpenTextFile(fso.BuildPath(fixtureDir, "generation_ledger.tsv"), 8, True, 0)

Set catia = CreateCatia()
catia.Visible = False
catia.DisplayFileAlerts = False
Set cfg = catia.SystemConfiguration
If cfg.Version <> 5 Or cfg.Release <> 21 Then Fatal "Expected CATIA V5R21, got " & RuntimeText(), 5
WScript.Echo "[CATIA] " & RuntimeText()

BuildSameReferenceProduct
BuildNestedProduct
BuildProductVersionPair

ledger.Close
catia.Quit
WScript.Echo "[DONE] CATProduct fixtures completed"
WScript.Quit 0

Sub BuildSameReferenceProduct()
  Dim finalPath, tmpPath, doc, root, products, files(0), c1, c2, matrix(11), ok
  finalPath = fso.BuildPath(fixtureDir, "product_same_reference_instances.CATProduct")
  tmpPath = TempPath("product_same_reference_instances.CATProduct")

  Set doc = NewProductDocument("CAA_PRODUCT_MULTI_INSTANCE")
  Set root = doc.Product
  root.Revision = "A"
  root.Nomenclature = "CAA same reference multi instance product"
  Set products = root.Products
  files(0) = partPath
  ComCall "PRODUCT-01 AddComponentsFromFiles A", products, "AddComponentsFromFiles", files, "All"
  ComCall "PRODUCT-01 AddComponentsFromFiles B", products, "AddComponentsFromFiles", files, "All"
  Set c1 = products.Item(1): c1.Name = "PadReference_Instance_A": c1.PartNumber = "PAD_REFERENCE_A"
  Set c2 = products.Item(2): c2.Name = "PadReference_Instance_B": c2.PartNumber = "PAD_REFERENCE_B"
  IdentityMatrix matrix
  matrix(0) = 0: matrix(1) = -1: matrix(2) = 0
  matrix(3) = 1: matrix(4) = 0: matrix(5) = 0
  matrix(9) = 140: matrix(10) = 20: matrix(11) = 0
  c2.Move.Apply matrix
  root.Update
  SaveClose doc, tmpPath

  ok = VerifyProductFile(tmpPath, "PRODUCT-01", 2, True, True)
  PromoteOrBlock tmpPath, finalPath, ok, "same CATPart reference, two instances, translation plus rotation"
End Sub

Sub BuildNestedProduct()
  Dim finalPath, tmpPath, doc, root, subA, subB, leafA, leafB, files(0), m(11), ok
  finalPath = fso.BuildPath(fixtureDir, "product_nested.CATProduct")
  tmpPath = TempPath("product_nested.CATProduct")

  Set doc = NewProductDocument("CAA_PRODUCT_NESTED")
  Set root = doc.Product
  root.Revision = "A"
  Set subA = root.Products.AddNewProduct("SUBASSEMBLY_A")
  subA.Name = "Assembly_Level_1_A"
  subA.PartNumber = "SUBASSEMBLY_A"
  files(0) = partPath
  subA.Products.AddComponentsFromFiles files, "All"
  Set leafA = subA.Products.Item(1)
  leafA.Name = "NestedPad_Level2_A"
  IdentityMatrix m: m(9) = 45: leafA.Move.Apply m

  Set subB = subA.Products.AddNewProduct("SUBASSEMBLY_B")
  subB.Name = "Assembly_Level_2_B"
  subB.PartNumber = "SUBASSEMBLY_B"
  IdentityMatrix m: m(10) = 80: subB.Move.Apply m
  subB.Products.AddComponentsFromFiles files, "All"
  Set leafB = subB.Products.Item(1)
  leafB.Name = "NestedPad_Level3_B"
  IdentityMatrix m
  m(0) = 0: m(1) = -1: m(3) = 1: m(4) = 0
  m(9) = 20: m(11) = 35
  leafB.Move.Apply m

  root.Update
  SaveClose doc, tmpPath
  ok = VerifyProductFile(tmpPath, "PRODUCT-02", 1, True, True)
  PromoteOrBlock tmpPath, finalPath, ok, "three-level nested product with parent/child transforms"
End Sub

Sub BuildProductVersionPair()
  Dim v1, v2, t1, t2, doc, root, products, files(0), m(11), ok1, ok2
  v1 = fso.BuildPath(fixtureDir, "version_product_v1.CATProduct")
  v2 = fso.BuildPath(fixtureDir, "version_product_v2.CATProduct")
  t1 = TempPath("version_product_v1.CATProduct")
  t2 = TempPath("version_product_v2.CATProduct")

  Set doc = NewProductDocument("CAA_PRODUCT_VERSION")
  Set root = doc.Product
  root.Revision = "A"
  Set products = root.Products
  files(0) = partPath
  products.AddComponentsFromFiles files, "All"
  products.Item(1).Name = "VersionPad_Base"
  root.Update
  doc.SaveAs t1

  products.AddComponentsFromFiles files, "All"
  products.Item(2).Name = "VersionPad_AddedInV2"
  IdentityMatrix m
  m(0) = 0: m(1) = -1: m(3) = 1: m(4) = 0
  m(9) = 90: m(11) = 15
  products.Item(2).Move.Apply m
  root.Revision = "B"
  root.Update
  SaveClose doc, t2

  ok1 = VerifyProductFile(t1, "VERSION-PRODUCT-01-v1", 1, True, False)
  ok2 = VerifyProductFile(t2, "VERSION-PRODUCT-01-v2", 2, True, True)
  PromoteOrBlock t1, v1, ok1 And ok2, "version pair v1 base BOM"
  PromoteOrBlock t2, v2, ok1 And ok2, "version pair v2 BOM add and transform change"
  If Not (ok1 And ok2) Then ledger.WriteLine "version_product_v1.CATProduct|version_product_v2.CATProduct" & vbTab & "blocked" & vbTab & RuntimeText() & vbTab & "close/reopen verification failed"
End Sub

Function NewProductDocument(ByVal partNumber)
  Dim doc
  Set doc = catia.Documents.Add("Product")
  doc.Product.PartNumber = partNumber
  Set NewProductDocument = doc
End Function

Sub SaveClose(ByVal doc, ByVal path)
  If fso.FileExists(path) Then fso.DeleteFile path, True
  Err.Clear
  On Error Resume Next
  doc.SaveAs path
  Dim e, d: e = Err.Number: d = Err.Description
  On Error GoTo 0
  If e <> 0 Then Fatal "SaveAs " & path & " 0x" & Hex(e) & " " & d, 20
  doc.Close
End Sub

Function VerifyProductFile(ByVal path, ByVal label, ByVal minRootChildren, ByVal requireReference, ByVal requireNonIdentity)
  Dim doc, root, childCount, totalNodes, nonIdentity, referencesOk
  VerifyProductFile = False
  Err.Clear
  On Error Resume Next
  Set doc = catia.Documents.Open(path)
  Dim e, d: e = Err.Number: d = Err.Description
  On Error GoTo 0
  If e <> 0 Then
    WScript.Echo "[VERIFY-ERROR] " & label & " open 0x" & Hex(e) & " " & d
    Exit Function
  End If
  Set root = doc.Product
  childCount = root.Products.Count
  totalNodes = 0: nonIdentity = False: referencesOk = True
  WalkProduct root, "", totalNodes, nonIdentity, referencesOk
  doc.Close
  If childCount < minRootChildren Then
    WScript.Echo "[VERIFY-ERROR] " & label & " root_children=" & childCount & " expected>=" & minRootChildren
    Exit Function
  End If
  If requireReference And Not referencesOk Then
    WScript.Echo "[VERIFY-ERROR] " & label & " external reference check failed"
    Exit Function
  End If
  If requireNonIdentity And Not nonIdentity Then
    WScript.Echo "[VERIFY-ERROR] " & label & " no non-identity instance transform found"
    Exit Function
  End If
  WScript.Echo "[REOPEN-OK] " & fso.GetFileName(path) & " root_children=" & childCount & " nodes=" & totalNodes & " non_identity_transform=" & nonIdentity
  VerifyProductFile = True
End Function

Sub WalkProduct(ByVal product, ByVal prefix, ByRef totalNodes, ByRef nonIdentity, ByRef referencesOk)
  Dim i, child, m(11)
  For i = 1 To product.Products.Count
    Set child = product.Products.Item(i)
    totalNodes = totalNodes + 1
    Err.Clear
    On Error Resume Next
    child.Position.GetComponents m
    If Err.Number <> 0 Then Err.Clear: IdentityMatrix m
    If Not child.ReferenceProduct Is Nothing Then
      Dim pn: pn = child.ReferenceProduct.PartNumber
      If Len(CStr(pn)) = 0 Then referencesOk = False
    End If
    On Error GoTo 0
    If Not IsIdentity(m) Then nonIdentity = True
    WalkProduct child, prefix & "/" & child.Name, totalNodes, nonIdentity, referencesOk
  Next
End Sub

Sub PromoteOrBlock(ByVal tmpPath, ByVal finalPath, ByVal ok, ByVal evidence)
  Dim name: name = fso.GetFileName(finalPath)
  If ok Then
    BackupExisting finalPath
    If fso.FileExists(finalPath) Then fso.DeleteFile finalPath, True
    fso.MoveFile tmpPath, finalPath
    ledger.WriteLine name & vbTab & "generated" & vbTab & RuntimeText() & vbTab & evidence
    WScript.Echo "[PROMOTED] " & name
  Else
    ledger.WriteLine name & vbTab & "blocked" & vbTab & RuntimeText() & vbTab & "temporary file retained=" & fso.GetFileName(tmpPath)
    WScript.Echo "[BLOCKED] " & name & "; temporary retained " & tmpPath
  End If
End Sub

Sub BackupExisting(ByVal path)
  If Not fso.FileExists(path) Then Exit Sub
  Dim stamped
  stamped = fso.BuildPath(backupDir, fso.GetBaseName(path) & "_" & Timestamp() & "." & fso.GetExtensionName(path))
  fso.CopyFile path, stamped, True
  WScript.Echo "[BACKUP] " & path & " -> " & stamped
End Sub

Function TempPath(ByVal name)
  TempPath = fso.BuildPath(fixtureDir, "__tmp_" & fso.GetBaseName(name) & "_" & Timestamp() & "." & fso.GetExtensionName(name))
End Function

Function CreateCatia()
  Err.Clear
  On Error Resume Next
  Set CreateCatia = CreateObject("CATIA.Application")
  Dim e, d: e = Err.Number: d = Err.Description
  On Error GoTo 0
  If e <> 0 Or CreateCatia Is Nothing Then
    WScript.Echo "[ERROR] Create CATIA.Application 0x" & Hex(e) & " " & d
    WScript.Quit 4
  End If
End Function

Sub ComCall(ByVal label, ByVal obj, ByVal method, ByRef files, ByVal mode)
  Err.Clear
  On Error Resume Next
  obj.AddComponentsFromFiles files, mode
  Dim e, d: e = Err.Number: d = Err.Description
  On Error GoTo 0
  If e <> 0 Then Fatal label & " failed 0x" & Hex(e) & " " & d, 21
End Sub

Sub IdentityMatrix(ByRef m)
  m(0)=1: m(1)=0: m(2)=0: m(3)=0: m(4)=1: m(5)=0
  m(6)=0: m(7)=0: m(8)=1: m(9)=0: m(10)=0: m(11)=0
End Sub

Function IsIdentity(ByRef m)
  IsIdentity = (Abs(CDbl(m(0))-1) < 0.000001 And Abs(CDbl(m(4))-1) < 0.000001 And Abs(CDbl(m(8))-1) < 0.000001 _
    And Abs(CDbl(m(1))) < 0.000001 And Abs(CDbl(m(2))) < 0.000001 And Abs(CDbl(m(3))) < 0.000001 _
    And Abs(CDbl(m(5))) < 0.000001 And Abs(CDbl(m(6))) < 0.000001 And Abs(CDbl(m(7))) < 0.000001 _
    And Abs(CDbl(m(9))) < 0.000001 And Abs(CDbl(m(10))) < 0.000001 And Abs(CDbl(m(11))) < 0.000001)
End Function

Function Timestamp()
  Dim n: n = Now
  Timestamp = Year(n) & Right("0" & Month(n), 2) & Right("0" & Day(n), 2) & "_" & Right("0" & Hour(n), 2) & Right("0" & Minute(n), 2) & Right("0" & Second(n), 2)
End Function

Function RuntimeText(): RuntimeText = "V" & cfg.Version & "R" & cfg.Release & "SP" & cfg.ServicePack: End Function
Sub Fatal(ByVal message, ByVal code)
  WScript.Echo "[ERROR] " & message
  On Error Resume Next
  If Not ledger Is Nothing Then ledger.Close
  If Not catia Is Nothing Then catia.Quit
  WScript.Quit code
End Sub
