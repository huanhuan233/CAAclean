#include "caa/CaaPartEnumerator.h"

#include <CATBaseUnknown.h>
#include <CATDocument.h>
#include <CATErrorDef.h>
#include <CATIContainer.h>
#include <CATInit.h>
#include <CATIPrtContainer.h>
#include <CATISpecObject.h>
#include <CATLISTV_CATISpecObject.h>
#include <CATUnicodeString.h>
#include <cstring>
#include <map>
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
  T*& Out() { return _ptr; }
  T* Get() const { return _ptr; }

private:
  CaaInterfaceGuard(const CaaInterfaceGuard&);
  CaaInterfaceGuard& operator=(const CaaInterfaceGuard&);
  T* _ptr;
};

class SpecListGuard
{
public:
  explicit SpecListGuard(CATListValCATISpecObject_var* list) : _list(list) {}
  ~SpecListGuard() { delete _list; }

private:
  SpecListGuard(const SpecListGuard&);
  SpecListGuard& operator=(const SpecListGuard&);
  CATListValCATISpecObject_var* _list;
};

class BaseUnknownSequenceGuard
{
public:
  explicit BaseUnknownSequenceGuard(SEQUENCE(CATBaseUnknown_ptr)& sequence) : _sequence(sequence) {}
  ~BaseUnknownSequenceGuard()
  {
    CATLONG32 index = 0;
    for (index = 0; index < _sequence.length(); ++index)
    {
      if (_sequence[index])
      {
        _sequence[index]->Release();
        _sequence[index] = 0;
      }
    }
  }

private:
  BaseUnknownSequenceGuard(const BaseUnknownSequenceGuard&);
  BaseUnknownSequenceGuard& operator=(const BaseUnknownSequenceGuard&);
  SEQUENCE(CATBaseUnknown_ptr)& _sequence;
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

static std::string SafeSpecString(CATISpecObject* spec, const char* field)
{
  if (!spec)
    return "";
  try
  {
    if (std::strcmp(field, "display") == 0)
      return UnicodeToUtf8Local(spec->GetDisplayName());
    if (std::strcmp(field, "internal") == 0)
      return UnicodeToUtf8Local(spec->GetName());
    if (std::strcmp(field, "startup") == 0)
      return UnicodeToUtf8Local(spec->GetType());
  }
  catch (...)
  {
  }
  return "";
}

static std::string MakeObjectId(long index)
{
  std::ostringstream out;
  out << "object_" << index;
  return out.str();
}

static std::string MakeOccurrenceId(long index)
{
  std::ostringstream out;
  out << "occurrence_" << index;
  return out.str();
}

static void AddStaticTreeNode(ReconstructionPackage& package,
                              const std::string& object_id,
                              const std::string& occurrence_id,
                              const std::string& parent_occurrence_id,
                              const std::string& object_kind,
                              const std::string& display_name,
                              const std::string& internal_name,
                              const std::string& startup_type,
                              const std::string& tree_path,
                              long source_index,
                              long container_index)
{
  ObjectEntity object;
  object.object_id = object_id;
  object.document_id = "doc_1";
  object.object_kind = object_kind;
  object.display_name = display_name;
  object.internal_name = internal_name;
  object.startup_type = startup_type;
  object.update_status = "unknown";
  object.capture_status = "available";
  object.identity.stable_id = object_id;
  object.identity.native_label = display_name.empty() ? internal_name : display_name;
  object.identity.scope = IdentitySessionLocal;
  object.identity.read_status = "runtime_verified";
  package.objects.push_back(object);

  ObjectOccurrence occurrence;
  occurrence.occurrence_id = occurrence_id;
  occurrence.object_id = object_id;
  occurrence.parent_occurrence_id = parent_occurrence_id;
  occurrence.document_id = "doc_1";
  occurrence.occurrence_path = tree_path;
  occurrence.tree_path = tree_path;
  occurrence.source_index = source_index;
  occurrence.container_index = container_index;
  occurrence.capture_status = "available";
  package.occurrence_graph.object_occurrences.push_back(occurrence);
}

class PartTreeCrawler
{
public:
  explicit PartTreeCrawler(ReconstructionPackage& package)
    : _package(package), _next_object_index(static_cast<long>(package.objects.size()) + 1),
      _next_occurrence_index(static_cast<long>(package.occurrence_graph.object_occurrences.size()) + 1)
  {
  }

  bool Visit(CATISpecObject* spec,
             const std::string& parent_occurrence_id,
             const std::string& parent_path,
             long source_index,
             long container_index,
             std::string& error)
  {
    if (!spec)
      return true;

    std::string object_id;
    std::map<CATISpecObject*, std::string>::iterator found = _object_ids.find(spec);
    if (found == _object_ids.end())
    {
      ObjectEntity object;
      object.object_id = MakeObjectId(_next_object_index++);
      object.document_id = "doc_1";
      object.object_kind = "catia_spec_object";
      object.display_name = SafeSpecString(spec, "display");
      object.internal_name = SafeSpecString(spec, "internal");
      object.startup_type = SafeSpecString(spec, "startup");
      object.update_status = "unknown";
      object.capture_status = "available";
      object.identity.stable_id = object.object_id;
      object.identity.native_label = object.display_name.empty() ? object.internal_name : object.display_name;
      object.identity.scope = IdentitySessionLocal;
      object.identity.read_status = "runtime_verified";
      object_id = object.object_id;
      _object_ids[spec] = object_id;
      _package.objects.push_back(object);
    }
    else
    {
      object_id = found->second;
    }

    std::string segment = SafeSpecString(spec, "display");
    if (segment.empty()) segment = SafeSpecString(spec, "internal");
    if (segment.empty()) segment = SafeSpecString(spec, "startup");
    if (segment.empty()) segment = "unnamed";
    const std::string path = parent_path + "/" + segment;

    ObjectOccurrence occurrence;
    occurrence.occurrence_id = MakeOccurrenceId(_next_occurrence_index++);
    occurrence.object_id = object_id;
    occurrence.parent_occurrence_id = parent_occurrence_id;
    occurrence.document_id = "doc_1";
    occurrence.occurrence_path = path;
    occurrence.tree_path = path;
    occurrence.source_index = source_index;
    occurrence.container_index = container_index;
    occurrence.capture_status = "available";
    _package.occurrence_graph.object_occurrences.push_back(occurrence);

    if (_expanded.find(spec) != _expanded.end())
      return true;
    _expanded[spec] = true;

    try
    {
      CATListValCATISpecObject_var* children = spec->ListComponents();
      if (!children)
        return true;
      SpecListGuard children_guard(children);
      int index = 0;
      for (index = 1; index <= children->Size(); ++index)
      {
        CATISpecObject_var child = (*children)[index];
        if (child != NULL_var)
        {
          CATISpecObject* child_pointer = child;
          Visit(child_pointer, occurrence.occurrence_id, path, index, container_index, error);
        }
      }
    }
    catch (...)
    {
      _package.diagnostics.push_back(MakeDiagnostic("warning", "object_traversal_failed", object_id,
                                                    "CATISpecObject::ListComponents failed; scan continued",
                                                    "part_enumerator"));
    }
    return true;
  }

private:
  ReconstructionPackage& _package;
  long _next_object_index;
  long _next_occurrence_index;
  std::map<CATISpecObject*, std::string> _object_ids;
  std::map<CATISpecObject*, bool> _expanded;
};

bool CaaPartEnumerator::Enumerate(CaaDocumentHandle& document_handle,
                                  ReconstructionPackage& package,
                                  std::string& error)
{
  if (package.document_graph.documents.empty() ||
      package.document_graph.documents[0].document_kind != "catpart")
  {
    return true;
  }

  CATDocument* document = static_cast<CATDocument*>(document_handle.NativeDocumentForCaaOnly());
  if (!document)
  {
    error = "null CATDocument";
    return false;
  }

  CATInit* init = 0;
  if (FAILED(document->QueryInterface(IID_CATInit, reinterpret_cast<void**>(&init))) || !init)
  {
    error = "CATInit is unavailable on CATPart document";
    return false;
  }
  CaaInterfaceGuard<CATInit> init_guard(init);

  CATBaseUnknown* root = init->GetRootContainer("CATIPrtContainer");
  if (!root)
  {
    error = "CATIPrtContainer root is unavailable";
    return false;
  }
  CaaInterfaceGuard<CATBaseUnknown> root_guard(root);

  CATIPrtContainer* part_container = 0;
  if (FAILED(root->QueryInterface(IID_CATIPrtContainer, reinterpret_cast<void**>(&part_container))) ||
      !part_container)
  {
    error = "CATIPrtContainer query failed";
    return false;
  }
  CaaInterfaceGuard<CATIPrtContainer> part_container_guard(part_container);

  AddStaticTreeNode(package, "object_1", "occurrence_1", "", "catia_document",
                    document_handle.DisplayName(), "CATDocument", "CATDocument",
                    "/document", 0, 0);
  AddStaticTreeNode(package, "object_2", "occurrence_2", "occurrence_1", "catia_container",
                    "PartSpecContainer", "CATIPrtContainer", "CATIPrtContainer",
                    "/document/PartSpecContainer", 1, 1);

  PartTreeCrawler crawler(package);
  CATISpecObject_var part = NULL_var;
  try
  {
    part = part_container->GetPart();
  }
  catch (...)
  {
    package.diagnostics.push_back(MakeDiagnostic("warning", "part_entry_exception", "doc_1",
                                                 "CATIPrtContainer::GetPart raised an exception",
                                                 "part_enumerator"));
    error = "Part root access failed";
    return false;
  }

  if (part == NULL_var)
  {
    error = "Part root is unavailable";
    return false;
  }

  CATISpecObject* part_pointer = part;
  if (!crawler.Visit(part_pointer, "occurrence_2", "/document/PartSpecContainer", 1, 1, error))
    return false;

  CATIContainer* generic_container = 0;
  if (SUCCEEDED(root->QueryInterface(IID_CATIContainer, reinterpret_cast<void**>(&generic_container))) &&
      generic_container)
  {
    CaaInterfaceGuard<CATIContainer> generic_container_guard(generic_container);
    try
    {
      SEQUENCE(CATBaseUnknown_ptr) members;
      BaseUnknownSequenceGuard members_guard(members);
      const CATLONG32 count = generic_container->ListMembersHere("CATISpecObject", members);
      CATLONG32 index = 0;
      for (index = 0; index < count; ++index)
      {
        CATBaseUnknown* member = members[index];
        if (!member)
          continue;
        CATISpecObject* member_spec = 0;
        if (SUCCEEDED(member->QueryInterface(IID_CATISpecObject, reinterpret_cast<void**>(&member_spec))) &&
            member_spec)
        {
          CaaInterfaceGuard<CATISpecObject> member_spec_guard(member_spec);
          crawler.Visit(member_spec, "", "/document/PartSpecContainer",
                        static_cast<long>(index + 1), 2, error);
        }
      }
    }
    catch (...)
    {
      package.diagnostics.push_back(MakeDiagnostic("warning", "container_enumeration_exception", "doc_1",
                                                   "CATIContainer::ListMembersHere failed; scan continued",
                                                   "part_enumerator"));
    }
  }
  else
  {
    package.diagnostics.push_back(MakeDiagnostic("info", "applicative_container_unavailable", "doc_1",
                                                 "root container does not expose CATIContainer",
                                                 "part_enumerator"));
  }

  package.diagnostics.push_back(MakeDiagnostic("info", "catpart_tree_captured", "doc_1",
                                               "CATPart specification tree captured from native CATDocument",
                                               "part_enumerator"));
  return true;
}

}
