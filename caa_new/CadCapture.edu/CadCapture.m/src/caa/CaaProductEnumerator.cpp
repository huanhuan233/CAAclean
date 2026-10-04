#include "caa/CaaProductEnumerator.h"
#include "caa/CaaParameterReader.h"
#include "caa/CaaPropertyEvidence.h"

#include <CATBaseUnknown.h>
#include <CATDocument.h>
#include <CATErrorDef.h>
#include <CATIDocRoots.h>
#include <CATILinkableObject.h>
#include <CATIProduct.h>
#include <CATIPrdProperties.h>
#include <CATIParmPublisher.h>
#include <CATICkeParm.h>
#include <CATISpecObject.h>
#include <CATLISTV_CATISpecObject.h>
#include <CATIMovable.h>
#include <CATLISTV_CATBaseUnknown.h>
#include <CATMathTransformation.h>
#include <CATUnicodeString.h>
#include <float.h>
#include <algorithm>
#include <cctype>
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

static void AppendProductField(ReconstructionPackage& package, CaptureIdRegistry& ids,
                               const std::string& subject, const char* group,
                               const char* key, const char* label,
                               CATIPrdProperties* properties,
                               HRESULT (CATIPrdProperties::*getter)(CATUnicodeString&))
{
  const std::string api = std::string("CATIPrdProperties.") + key;
  PropertyFact fact = evidence::Failure(properties ? "failed" : "unsupported", api);
  if (properties)
  {
    try
    {
      CATUnicodeString value;
      if (SUCCEEDED((properties->*getter)(value))) fact = evidence::Text(UnicodeToUtf8Local(value), api);
    }
    catch (...) { fact.read_status = "exception"; }
  }
  evidence::Append(ids, package, subject, group, key, label, fact);
}

static void CaptureProductProperties(CATBaseUnknown* product, const std::string& subject,
                                     bool reference, CaptureIdRegistry& ids,
                                     ReconstructionPackage& package)
{
  CATIPrdProperties* raw = 0;
  if (product)
  {
    try { product->QueryInterface(IID_CATIPrdProperties, reinterpret_cast<void**>(&raw)); }
    catch (...) { raw = 0; }
  }
  CaaInterfaceGuard<CATIPrdProperties> guard(raw);
  CATIPrdProperties* properties = guard.Get();
  const char* group = reference ? "product_reference" : "product_instance";
  if (reference)
  {
    AppendProductField(package, ids, subject, group, "PartNumber", "Part number", properties, &CATIPrdProperties::GetPartNumber);
    AppendProductField(package, ids, subject, group, "Revision", "Revision", properties, &CATIPrdProperties::GetRevision);
    AppendProductField(package, ids, subject, group, "Definition", "Definition", properties, &CATIPrdProperties::GetDefinition);
    AppendProductField(package, ids, subject, group, "Nomenclature", "Nomenclature", properties, &CATIPrdProperties::GetNomenclature);
    AppendProductField(package, ids, subject, group, "DescriptionRef", "Reference description", properties, &CATIPrdProperties::GetDescriptionRef);
    PropertyFact source = evidence::Failure(properties ? "failed" : "unsupported", "CATIPrdProperties.GetSource");
    if (properties)
    {
      try
      {
        CatProductSource value = catProductSourceUnknown;
        if (SUCCEEDED(properties->GetSource(value)))
        {
          source = evidence::Text(evidence::Number(static_cast<long>(value)), "CATIPrdProperties.GetSource");
          source.value_type = "enum";
          source.display_value = value == catProductMade ? "自制" :
                                 value == catProductBought ? "外购" :
                                 value == catProductSourceUnknown ? "未知" : "unrecognized_enum";
        }
      }
      catch (...) { source.read_status = "exception"; }
    }
    evidence::Append(ids, package, subject, group, "Source", "Source", source);
    if (!properties) return;
    CATIParmPublisher* publisher = 0;
    try
    {
      if (FAILED(properties->GetUserProperties(publisher, FALSE)) || !publisher)
      {
        evidence::Append(ids, package, subject, "product_custom", "read_status", "Custom attributes",
                         evidence::Failure("unavailable", "CATIPrdProperties.GetUserProperties"));
        return;
      }
      CaaInterfaceGuard<CATIParmPublisher> publisher_guard(publisher);
      CATListValCATISpecObject_var children;
      publisher->GetDirectChildren("CATICkeParm", children);
      for (int i = 1; i <= children.Size(); ++i)
      {
        CATISpecObject_var child = children[i];
        CATICkeParm* parameter = 0;
        if (child == NULL_var || FAILED(child->QueryInterface(IID_CATICkeParm, reinterpret_cast<void**>(&parameter))) || !parameter)
          continue;
        CaaInterfaceGuard<CATICkeParm> parameter_guard(parameter);
        PropertyFact fact = ReadCaaParameter(parameter);
        std::string path;
        try { path = UnicodeToUtf8Local(parameter->Pathname()); } catch (...) {}
        if (path.empty()) path = fact.display_name;
        const std::string::size_type separator = path.find_last_of("/\\");
        const std::string short_name = separator == std::string::npos ? path : path.substr(separator + 1);
        evidence::Append(ids, package, subject, "product_custom", "custom:" + path,
                         short_name, fact);
        PropertyFact role = evidence::Failure("unavailable", "CATICkeParm.InternalRole");
        try { role = evidence::Text(UnicodeToUtf8Local(parameter->InternalRole()), "CATICkeParm.InternalRole"); }
        catch (...) { role.read_status = "exception"; }
        evidence::Append(ids, package, subject, "product_custom", "custom:" + path + ":internal_role",
                         short_name + " role", role);
      }
    }
    catch (...)
    {
      evidence::Append(ids, package, subject, "product_custom", "read_status", "Custom attributes",
                       evidence::Failure("exception", "CATIParmPublisher.GetDirectChildren"));
    }
  }
  else
  {
    AppendProductField(package, ids, subject, group, "InstanceName", "Instance name", properties, &CATIPrdProperties::GetInstanceName);
    AppendProductField(package, ids, subject, group, "DescriptionInst", "Instance description", properties, &CATIPrdProperties::GetDescriptionInst);
  }
}

static void CapturePartKnowledgeParameters(CATBaseUnknown* part_root,
                                           const std::string& document_id,
                                           CaptureIdRegistry& ids,
                                           ReconstructionPackage& package)
{
  CATIParmPublisher* publisher = 0;
  try
  {
    if (!part_root || FAILED(part_root->QueryInterface(IID_CATIParmPublisher,
        reinterpret_cast<void**>(&publisher))) || !publisher)
    {
      evidence::Append(ids, package, document_id, "mbd_knowledge", "read_status",
        "Knowledge parameters", evidence::Failure("unsupported", "CATIParmPublisher.GetAllChildren"));
      return;
    }
    CaaInterfaceGuard<CATIParmPublisher> guard(publisher);
    CATListValCATISpecObject_var children;
    publisher->GetAllChildren("CATICkeParm", children);
    for (int i = 1; i <= children.Size(); ++i)
    {
      CATISpecObject_var child = children[i];
      CATICkeParm* parameter = 0;
      if (child == NULL_var || FAILED(child->QueryInterface(IID_CATICkeParm,
          reinterpret_cast<void**>(&parameter))) || !parameter) continue;
      CaaInterfaceGuard<CATICkeParm> parameter_guard(parameter);
      PropertyFact fact = ReadCaaParameter(parameter);
      std::string path;
      try { path = UnicodeToUtf8Local(parameter->Pathname()); } catch (...) {}
      if (path.empty()) path = fact.display_name;
      evidence::Append(ids, package, document_id, "mbd_knowledge", "knowledge:" + path,
                       fact.display_name, fact);
      PropertyFact role = evidence::Failure("unavailable", "CATICkeParm.InternalRole");
      try { role = evidence::Text(UnicodeToUtf8Local(parameter->InternalRole()), "CATICkeParm.InternalRole"); }
      catch (...) { role.read_status = "exception"; }
      evidence::Append(ids, package, document_id, "mbd_knowledge", "knowledge:" + path + ":internal_role",
                       fact.display_name + " role", role);
    }
  }
  catch (...)
  {
    evidence::Append(ids, package, document_id, "mbd_knowledge", "read_status",
      "Knowledge parameters", evidence::Failure("exception", "CATIParmPublisher.GetAllChildren"));
  }
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

static std::string LowerCopy(const std::string& value)
{
  std::string lowered = value;
  std::transform(lowered.begin(), lowered.end(), lowered.begin(), static_cast<int (*)(int)>(::tolower));
  return lowered;
}

static std::string DocumentKindFromName(const std::string& name)
{
  const std::string lowered = LowerCopy(name);
  if (lowered.size() >= 8 && lowered.substr(lowered.size() - 8) == ".catpart")
    return "catpart";
  if (lowered.size() >= 11 && lowered.substr(lowered.size() - 11) == ".catproduct")
    return "catproduct";
  return "unknown";
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
  ProductCrawler(ReconstructionPackage& package, CaptureIdRegistry& ids,
                 CATDocument* root_document, const std::string& document_id)
    : _package(package), _ids(ids), _root_document(root_document), _document_id(document_id)
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

    CATIProduct_var reference = NULL_var;
    try { reference = product->GetReferenceProduct(); }
    catch (...)
    {
      _package.diagnostics.push_back(MakeDiagnostic("warning", "product_reference_unavailable",
                                                    parent_occurrence_id.empty() ? _document_id : parent_occurrence_id,
                                                    "CATIProduct::GetReferenceProduct failed; instance kept with local product identity",
                                                    "product_enumerator"));
    }
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

    ProductReferenceEntity* reference_entity = ReferenceEntity(reference_product, part_number);
    std::string reference_id = reference_entity ? reference_entity->reference_id : "";
    std::string occurrence_id = _ids.NextProductOccurrenceId();
    const std::string tree_path = parent_tree_path.empty() ? ("/" + instance_name) : (parent_tree_path + "/" + instance_name);
    const std::string occurrence_path = parent_occurrence_path.empty() ? ("/" + MachineSegment(source_index, instance_name)) :
                                      (parent_occurrence_path + "/" + MachineSegment(source_index, instance_name));

    ProductOccurrence occurrence;
    occurrence.occurrence_id = occurrence_id;
    occurrence.parent_occurrence_id = parent_occurrence_id;
    occurrence.reference_id = reference_id;
    occurrence.referenced_document_id = reference_entity ? reference_entity->referenced_document_id : "";
    occurrence.instance_name = instance_name;
    occurrence.part_number = part_number;
    occurrence.tree_path = tree_path;
    occurrence.occurrence_path = occurrence_path;
    occurrence.depth = depth;
    occurrence.source_index = source_index;
    occurrence.load_status = (reference_entity && reference_entity->referenced_document_id.empty()) ? "unresolved" : "loaded";
    occurrence.capture_status = "available";
    occurrence.presentation_status = "visible";
    try { occurrence.child_count = product->GetChildrenCount(); }
    catch (...) { occurrence.child_count = 0; }
    ReadAbsTransform(product, occurrence, _package);
    _package.product_occurrences.push_back(occurrence);
    CaptureProductProperties(product, occurrence_id, false, _ids, _package);

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
  std::string PointerKey(const void* pointer) const
  {
    std::ostringstream out;
    out << pointer;
    return out.str();
  }

  CATDocument* ReferenceDocument(CATIProduct* reference_product) const
  {
    if (!reference_product)
      return 0;
    CATILinkableObject* linkable = 0;
    try
    {
      if (FAILED(reference_product->QueryInterface(IID_CATILinkableObject,
          reinterpret_cast<void**>(&linkable))) || !linkable)
        return 0;
      CaaInterfaceGuard<CATILinkableObject> linkable_guard(linkable);
      return linkable->GetDocument();
    }
    catch (...)
    {
    }
    return 0;
  }

  ProductReferenceEntity* ReferenceEntity(CATIProduct* reference_product, const std::string& part_number)
  {
    CATDocument* reference_document = ReferenceDocument(reference_product);
    std::string reference_document_name;
    if (reference_document)
      reference_document_name = UnicodeToUtf8Local(reference_document->DisplayName());

    std::string key;
    if (reference_document)
      key = "document_session|" + PointerKey(reference_document) + "|" + PointerKey(reference_product);
    else
      key = "session_reference|" + PointerKey(reference_product);
    std::map<std::string, std::string>::iterator found = _references.find(key);
    if (found != _references.end())
      return FindReference(found->second);

    const std::string reference_id = _ids.NextProductReferenceId();
    _references[key] = reference_id;

    ProductReferenceEntity reference;
    reference.reference_id = reference_id;
    if (reference_document && reference_document == _root_document)
      reference.referenced_document_id = _document_id;
    else if (reference_document && !reference_document_name.empty())
      reference.referenced_document_id = EnsureLinkedDocument(reference_document, reference_document_name, reference_id);
    reference.part_number = part_number;
    reference.display_name = part_number;
    reference.reference_document_name = reference_document_name;
    if (reference_document && reference_document == _root_document)
      reference.reference_document_kind = "catproduct";
    else if (reference_document)
      reference.reference_document_kind = DocumentKindFromName(reference_document_name);
    else
      reference.reference_document_kind = "unresolved";
    reference.definition_status = reference.referenced_document_id.empty() ? "unresolved_reference_document" : "same_document_product_reference";
    reference.value_source = "CATIProduct";
    reference.identity_method = reference_document ? "session_document_and_reference_product" : "session_reference_product_object";
    _package.product_references.push_back(reference);
    ProductReferenceEntity* stored = &_package.product_references[_package.product_references.size() - 1];
    CaptureProductProperties(reference_product, reference_id, true, _ids, _package);

    if (reference.referenced_document_id.empty())
    {
      _package.diagnostics.push_back(MakeDiagnostic("warning", "product_reference_document_unresolved",
                                                    reference_id,
                                                    "Reference Product identity is session-local and its owning CATDocument could not be mapped to a captured document",
                                                    "product_enumerator"));
    }
    return stored;
  }

  std::string EnsureLinkedDocument(CATDocument* document,
                                   const std::string& document_name,
                                   const std::string& reference_id)
  {
    std::map<CATDocument*, std::string>::iterator found = _document_ids_by_pointer.find(document);
    if (found != _document_ids_by_pointer.end())
      return found->second;

    DocumentEntity entity;
    entity.document_id = _ids.NextDocumentId();
    entity.document_kind = DocumentKindFromName(document_name);
    entity.source_file_name = document_name;
    entity.display_name = document_name;
    entity.load_status = "loaded";
    entity.capture_status = "referenced";
    entity.native_document_open_status = "provided_by_CATILinkableObject";
    entity.definition_status = "reference_document_not_parsed";
    entity.identity_method = "CATILinkableObject.GetDocument";
    _package.document_graph.AddDocument(entity);
    _document_ids_by_pointer[document] = entity.document_id;
    NativeDocumentBinding binding;
    binding.document_id = entity.document_id;
    binding.native_document = document;
    _package.native_document_bindings.push_back(binding);

    DocumentLink link;
    link.link_id = _ids.NextDocumentLinkId();
    link.from_document_id = _document_id;
    link.to_document_id = entity.document_id;
    link.reference_id = reference_id;
    link.link_role = "product_reference";
    link.link_status = "loaded";
    link.value_source = "CATILinkableObject.GetDocument";
    link.read_status = "available";
    _package.document_graph.links.push_back(link);
    return entity.document_id;
  }

  ProductReferenceEntity* FindReference(const std::string& reference_id)
  {
    size_t i;
    for (i = 0; i < _package.product_references.size(); ++i)
    {
      if (_package.product_references[i].reference_id == reference_id)
        return &_package.product_references[i];
    }
    return 0;
  }

  ReconstructionPackage& _package;
  CaptureIdRegistry& _ids;
  CATDocument* _root_document;
  std::string _document_id;
  std::map<std::string, std::string> _references;
  std::map<CATDocument*, std::string> _document_ids_by_pointer;
  std::set<std::string> _active_references;
};

bool CaaProductEnumerator::Enumerate(CaaDocumentHandle& document_handle,
                                     CaptureIdRegistry& ids,
                                     ReconstructionPackage& package,
                                     std::string& error)
{
  if (package.document_graph.documents.empty())
    return true;
  const std::string document_kind = package.document_graph.documents[0].document_kind;
  if (document_kind != "catproduct" && document_kind != "catpart") return true;

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

  if (document_kind == "catpart")
  {
    CaptureProductProperties(root_base, package.document_graph.documents[0].document_id, true, ids, package);
    CapturePartKnowledgeParameters(root_base, package.document_graph.documents[0].document_id, ids, package);
    return true;
  }

  CATIProduct* root_product = 0;
  if (FAILED(root_base->QueryInterface(IID_CATIProduct, reinterpret_cast<void**>(&root_product))) ||
      !root_product)
  {
    error = "CATProduct document root does not expose CATIProduct";
    return false;
  }
  CaaInterfaceGuard<CATIProduct> root_product_guard(root_product);

  ProductCrawler crawler(package, ids, document, package.document_graph.documents[0].document_id);
  crawler.Visit(root_product, "", "", "", 0, 0);
  package.diagnostics.push_back(MakeDiagnostic("info", "catproduct_bom_captured", package.document_graph.documents[0].document_id,
                                               "CATProduct multi-level BOM captured from native CATDocument",
                                               "product_enumerator"));
  return true;
}

}
