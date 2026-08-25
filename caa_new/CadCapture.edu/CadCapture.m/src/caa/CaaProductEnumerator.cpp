#include "caa/CaaProductEnumerator.h"

#include <CATBaseUnknown.h>
#include <CATDocument.h>
#include <CATErrorDef.h>
#include <CATIDocRoots.h>
#include <CATIProduct.h>
#include <CATIMovable.h>
#include <CATLISTV_CATBaseUnknown.h>
#include <CATMathTransformation.h>
#include <CATUnicodeString.h>
#include <float.h>
#include <map>
#include <set>
#include <sstream>
#include <vector>

namespace cadcapture {

template <class T>
class CaaInterfaceGuard
{
public:
  CaaInterfaceGuard() : _ptr(0) {}
  explicit CaaInterfaceGuard(T* ptr) : _ptr(ptr) {}
  ~CaaInterfaceGuard() { if (_ptr) _ptr->Release(); }
  T* Get() const { return _ptr; }

private:
  CaaInterfaceGuard(const CaaInterfaceGuard&);
  CaaInterfaceGuard& operator=(const CaaInterfaceGuard&);
  T* _ptr;
};

class BaseUnknownListGuard
{
public:
  explicit BaseUnknownListGuard(CATListValCATBaseUnknown_var* list) : _list(list) {}
  ~BaseUnknownListGuard() { delete _list; }

private:
  BaseUnknownListGuard(const BaseUnknownListGuard&);
  BaseUnknownListGuard& operator=(const BaseUnknownListGuard&);
  CATListValCATBaseUnknown_var* _list;
};

static std::string UnicodeToUtf8Local(const CATUnicodeString& value)
{
  const size_t capacity = static_cast<size_t>(value.GetLengthInChar() + 1) * 4 + 1;
  std::vector<char> buffer(capacity, 0);
  size_t byte_count = 0;
  value.ConvertToUTF8(&buffer[0], &byte_count);
  if (byte_count >= buffer.size())
    byte_count = buffer.size() - 1;
  buffer[byte_count] = 0;
  return std::string(&buffer[0], byte_count);
}

static std::string MakeProductReferenceId(long index)
{
  std::ostringstream out;
  out << "product_reference_" << index;
  return out.str();
}

static std::string MakeProductOccurrenceId(long index)
{
  std::ostringstream out;
  out << "product_occurrence_" << index;
  return out.str();
}

static std::string MachineSegment(long index, const std::string& name)
{
  std::ostringstream out;
  out << index << ":" << name;
  return out.str();
}

static bool IsFinite(double value)
{
  return _finite(value) != 0;
}

static bool ReadAbsTransform(CATIProduct* product, ProductOccurrence& occurrence,
                             ReconstructionPackage& package)
{
  if (occurrence.depth == 0)
  {
    occurrence.transform_status = "identity_root";
    occurrence.transform_source = "CATProduct.root";
    return true;
  }
  CATIMovable* movable = 0;
  if (FAILED(product->QueryInterface(IID_CATIMovable, reinterpret_cast<void**>(&movable))) ||
      !movable)
  {
    occurrence.transform_status = "unavailable";
    occurrence.transform_source = "CATIMovable";
    package.diagnostics.push_back(MakeDiagnostic("warning", "product_transform_unavailable",
                                                 occurrence.occurrence_id,
                                                 "CATIProduct instance does not expose CATIMovable",
                                                 "product_enumerator"));
    return false;
  }
  CaaInterfaceGuard<CATIMovable> movable_guard(movable);
  CATMathTransformation position;
  if (FAILED(movable->GetAbsPosition(position)))
  {
    occurrence.transform_status = "failed";
    occurrence.transform_source = "CATIMovable.GetAbsPosition";
    package.diagnostics.push_back(MakeDiagnostic("warning", "product_transform_failed",
                                                 occurrence.occurrence_id,
                                                 "CATIMovable::GetAbsPosition failed",
                                                 "product_enumerator"));
    return false;
  }
  double coeff[12];
  if (FAILED(position.GetCoefficients(coeff, 12)))
  {
    occurrence.transform_status = "failed";
    occurrence.transform_source = "CATMathTransformation.GetCoefficients";
    package.diagnostics.push_back(MakeDiagnostic("warning", "product_transform_coefficients_failed",
                                                 occurrence.occurrence_id,
                                                 "CATMathTransformation::GetCoefficients failed",
                                                 "product_enumerator"));
    return false;
  }
  int i;
  for (i = 0; i < 12; ++i)
  {
    if (!IsFinite(coeff[i]))
    {
      occurrence.transform_status = "failed";
      occurrence.transform_source = "CATMathTransformation.GetCoefficients";
      return false;
    }
  }
  occurrence.transform_4x4.clear();
  occurrence.transform_4x4.push_back(coeff[0]);
  occurrence.transform_4x4.push_back(coeff[3]);
  occurrence.transform_4x4.push_back(coeff[6]);
  occurrence.transform_4x4.push_back(coeff[9]);
  occurrence.transform_4x4.push_back(coeff[1]);
  occurrence.transform_4x4.push_back(coeff[4]);
  occurrence.transform_4x4.push_back(coeff[7]);
  occurrence.transform_4x4.push_back(coeff[10]);
  occurrence.transform_4x4.push_back(coeff[2]);
  occurrence.transform_4x4.push_back(coeff[5]);
  occurrence.transform_4x4.push_back(coeff[8]);
  occurrence.transform_4x4.push_back(coeff[11]);
  occurrence.transform_4x4.push_back(0.0);
  occurrence.transform_4x4.push_back(0.0);
  occurrence.transform_4x4.push_back(0.0);
  occurrence.transform_4x4.push_back(1.0);
  occurrence.transform_status = "resolved_absolute";
  occurrence.transform_source = "CATIMovable.GetAbsPosition";
  return true;
}

class ProductCrawler
{
public:
  ProductCrawler(ReconstructionPackage& package, const std::string& document_id)
    : _package(package), _document_id(document_id), _next_reference(1), _next_occurrence(1)
  {
  }

  bool Visit(CATIProduct* product,
             const std::string& parent_occurrence_id,
             const std::string& parent_tree_path,
             const std::string& parent_occurrence_path,
             long depth,
             long source_index)
  {
    if (!product)
      return true;

    CATIProduct_var reference = product->GetReferenceProduct();
    CATIProduct* reference_product = reference;
    if (!reference_product)
      reference_product = product;

    std::string instance_name;
    try
    {
      CATUnicodeString name;
      if (SUCCEEDED(product->GetPrdInstanceName(name)))
        instance_name = UnicodeToUtf8Local(name);
    }
    catch (...) {}

    std::string part_number;
    try { part_number = UnicodeToUtf8Local(reference_product->GetPartNumber()); }
    catch (...) {}
    if (instance_name.empty())
      instance_name = part_number.empty() ? "Product" : part_number;

    std::string reference_id = ReferenceId(reference_product, part_number);
    std::string occurrence_id = MakeProductOccurrenceId(_next_occurrence++);
    const std::string tree_path = parent_tree_path.empty() ? ("/" + instance_name) : (parent_tree_path + "/" + instance_name);
    const std::string occurrence_path = parent_occurrence_path.empty() ? ("/" + MachineSegment(source_index, instance_name)) :
                                      (parent_occurrence_path + "/" + MachineSegment(source_index, instance_name));

    ProductOccurrence occurrence;
    occurrence.occurrence_id = occurrence_id;
    occurrence.parent_occurrence_id = parent_occurrence_id;
    occurrence.reference_id = reference_id;
    occurrence.referenced_document_id = _document_id;
    occurrence.instance_name = instance_name;
    occurrence.part_number = part_number;
    occurrence.tree_path = tree_path;
    occurrence.occurrence_path = occurrence_path;
    occurrence.depth = depth;
    occurrence.source_index = source_index;
    occurrence.load_status = "loaded";
    occurrence.capture_status = "available";
    occurrence.presentation_status = "visible";
    try { occurrence.child_count = product->GetChildrenCount(); }
    catch (...) { occurrence.child_count = 0; }
    ReadAbsTransform(product, occurrence, _package);
    _package.product_occurrences.push_back(occurrence);

    if (_active_references.find(reference_id) != _active_references.end())
    {
      _package.diagnostics.push_back(MakeDiagnostic("warning", "product_cycle", occurrence_id,
                                                    "Product reference appeared again in the active recursion path; subtree expansion stopped",
                                                    "product_enumerator"));
      return true;
    }
    _active_references.insert(reference_id);

    CATListValCATBaseUnknown_var* children = 0;
    try { children = product->GetChildren("CATIProduct"); }
    catch (...) { children = 0; }
    if (children)
    {
      BaseUnknownListGuard children_guard(children);
      int index = 1;
      for (; index <= children->Size(); ++index)
      {
        CATBaseUnknown_var child_unknown = (*children)[index];
        CATBaseUnknown* child_base = child_unknown;
        if (!child_base)
          continue;
        CATIProduct* child_product = 0;
        if (SUCCEEDED(child_base->QueryInterface(IID_CATIProduct,
            reinterpret_cast<void**>(&child_product))) && child_product)
        {
          CaaInterfaceGuard<CATIProduct> child_guard(child_product);
          Visit(child_product, occurrence_id, tree_path, occurrence_path, depth + 1, index);
        }
      }
    }
    else if (occurrence.child_count > 0)
    {
      _package.diagnostics.push_back(MakeDiagnostic("warning", "product_children_unavailable", occurrence_id,
                                                    "CATIProduct::GetChildren returned null",
                                                    "product_enumerator"));
    }

    _active_references.erase(reference_id);
    return true;
  }

private:
  std::string ReferenceId(CATIProduct* reference_product, const std::string& part_number)
  {
    (void)reference_product;
    std::string key = _document_id + "|";
    key += part_number.empty() ? "unnamed_product_reference" : part_number;
    std::map<std::string, std::string>::iterator found = _references.find(key);
    if (found != _references.end())
      return found->second;
    const std::string reference_id = MakeProductReferenceId(_next_reference++);
    _references[key] = reference_id;

    ProductReferenceEntity reference;
    reference.reference_id = reference_id;
    reference.referenced_document_id = _document_id;
    reference.part_number = part_number;
    reference.display_name = part_number;
    reference.reference_document_kind = "catproduct";
    reference.definition_status = "same_document_product_reference";
    reference.value_source = "CATIProduct";
    reference.identity_method = part_number.empty() ? "canonical_unknown_identity" : "document_part_number_reference";
    _package.product_references.push_back(reference);
    return reference_id;
  }

  ReconstructionPackage& _package;
  std::string _document_id;
  long _next_reference;
  long _next_occurrence;
  std::map<std::string, std::string> _references;
  std::set<std::string> _active_references;
};

bool CaaProductEnumerator::Enumerate(CaaDocumentHandle& document_handle,
                                     ReconstructionPackage& package,
                                     std::string& error)
{
  if (package.document_graph.documents.empty() ||
      package.document_graph.documents[0].document_kind != "catproduct")
    return true;

  CATDocument* document = static_cast<CATDocument*>(document_handle.NativeDocumentForCaaOnly());
  if (!document)
  {
    error = "null CATDocument";
    return false;
  }

  CATIDocRoots* doc_roots = 0;
  if (FAILED(document->QueryInterface(IID_CATIDocRoots, reinterpret_cast<void**>(&doc_roots))) ||
      !doc_roots)
  {
    error = "CATIDocRoots is unavailable on CATProduct document";
    return false;
  }
  CaaInterfaceGuard<CATIDocRoots> roots_guard(doc_roots);

  CATListValCATBaseUnknown_var* roots = 0;
  try { roots = doc_roots->GiveDocRoots(); }
  catch (...) { roots = 0; }
  if (!roots || roots->Size() == 0)
  {
    delete roots;
    error = "CATProduct document has no document root product";
    return false;
  }
  BaseUnknownListGuard roots_list_guard(roots);
  CATBaseUnknown_var root_unknown = (*roots)[1];
  CATBaseUnknown* root_base = root_unknown;
  if (!root_base)
  {
    error = "CATProduct root object is null";
    return false;
  }

  CATIProduct* root_product = 0;
  if (FAILED(root_base->QueryInterface(IID_CATIProduct, reinterpret_cast<void**>(&root_product))) ||
      !root_product)
  {
    error = "CATProduct document root does not expose CATIProduct";
    return false;
  }
  CaaInterfaceGuard<CATIProduct> root_product_guard(root_product);

  ProductCrawler crawler(package, package.document_graph.documents[0].document_id);
  crawler.Visit(root_product, "", "", "", 0, 0);
  package.diagnostics.push_back(MakeDiagnostic("info", "catproduct_bom_captured", "doc_1",
                                               "CATProduct multi-level BOM captured from native CATDocument",
                                               "product_enumerator"));
  return true;
}

}
