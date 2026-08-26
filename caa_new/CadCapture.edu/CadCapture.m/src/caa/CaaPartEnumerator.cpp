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

static std::string SafeUpdateStatus(CATISpecObject* spec)
{
  if (!spec)
    return "unavailable";
  try
  {
    return spec->IsUpToDate() ? "up_to_date" : "not_up_to_date";
  }
  catch (...)
  {
  }
  return "unavailable";
}

static std::string DisplaySegment(CATISpecObject* spec)
{
  std::string segment = SafeSpecString(spec, "display");
  if (segment.empty()) segment = SafeSpecString(spec, "internal");
  if (segment.empty()) segment = SafeSpecString(spec, "startup");
  if (segment.empty()) segment = "unnamed";
  return segment;
}

static void ReleaseSpecList(std::vector<CATISpecObject*>& specs)
{
  size_t i;
  for (i = 0; i < specs.size(); ++i)
  {
    if (specs[i])
      specs[i]->Release();
  }
  specs.clear();
}

static std::string MakeMachineSegment(long source_index, const std::string& segment)
{
  std::ostringstream out;
  out << source_index << ":" << segment;
  return out.str();
}

static std::string JoinDisplayPath(const std::string& prefix, const std::string& segment)
{
  if (prefix.empty())
    return "/" + segment;
  return prefix + "/" + segment;
}

static std::string JoinMachinePath(const std::string& prefix, long source_index, const std::string& segment)
{
  if (prefix.empty())
    return "/" + MakeMachineSegment(source_index, segment);
  return prefix + "/" + MakeMachineSegment(source_index, segment);
}

static bool EndsWithPathSegment(const std::string& path, const std::string& segment)
{
  if (path.size() < segment.size())
    return false;
  if (path.compare(path.size() - segment.size(), segment.size(), segment) != 0)
    return false;
  return path.size() == segment.size() || path[path.size() - segment.size() - 1] == '/';
}

static long FeaturePropertyChildOrder(const std::string& parent_tree_path, const std::string& display_name)
{
  if (!EndsWithPathSegment(parent_tree_path, "\xE7\x89\xB9\xE5\xBE\x81\xE5\xB1\x9E\xE6\x80\xA7"))
    return 0;

  if (display_name == "\xE9\xA1\xB6\xE9\x9D\xA2\xE6\xA0\x87\xE8\xAF\x86")
    return 1;
  if (display_name == "\xE4\xBE\xA7\xE5\xA3\x81\xE7\xB1\xBB\xE5\x9E\x8B")
    return 2;
  if (display_name == "\xE5\xBA\x95\xE8\xA7\x92\xE5\x8D\x8A\xE5\xBE\x84")
    return 3;
  if (display_name == "\xE5\x8C\x85\xE5\x9B\xB4\xE7\x9B\x92")
    return 4;
  if (display_name == "\xE5\xBA\x95\xE9\x9D\xA2\xE6\xA0\x87\xE8\xAF\x86")
    return 5;
  if (display_name == "\xE5\xBA\x95\xE9\x9D\xA2\xE6\xB3\x95\xE5\x90\x91")
    return 6;
  if (display_name == "\xE8\xBD\xAC\xE8\xA7\x92\xE5\x8D\x8A\xE5\xBE\x84")
    return 7;
  if (display_name == "\xE6\x98\xAF\xE5\x90\xA6\xE5\x85\xB1\xE4\xBE\xA7\xE9\x9D\xA2")
    return 8;
  if (display_name == "\xE5\xB1\x82\xE6\x95\xB0")
    return 9;

  return 0;
}

static ObjectEntity MakeStaticObject(CaptureIdRegistry& ids,
                                     const std::string& document_id,
                                     const std::string& object_kind,
                                     const std::string& display_name,
                                     const std::string& internal_name,
                                     const std::string& startup_type)
{
  ObjectEntity object;
  object.object_id = ids.NextObjectId();
  object.document_id = document_id;
  object.object_kind = object_kind;
  object.display_name = display_name;
  object.internal_name = internal_name;
  object.startup_type = startup_type;
  object.update_status = "not_applicable";
  object.capture_status = "available";
  object.identity.capture_id = object.object_id;
  object.identity.identity_method = "static_document_definition_node";
  object.identity.native_label = display_name.empty() ? internal_name : display_name;
  object.identity.scope = IdentitySessionLocal;
  object.identity.read_status = "session_local_only";
  return object;
}

static ObjectOccurrence MakeTemplateOccurrence(const std::string& template_id,
                                               const std::string& object_id,
                                               const std::string& parent_template_id,
                                               const std::string& document_id,
                                               const std::string& tree_path,
                                               const std::string& occurrence_path,
                                               long source_index,
                                               long container_index,
                                               const std::string& occurrence_role,
                                               const std::string& enumeration_source,
                                               const std::string& presentation_status)
{
  ObjectOccurrence occurrence;
  occurrence.occurrence_id = template_id;
  occurrence.object_id = object_id;
  occurrence.parent_occurrence_id = parent_template_id;
  occurrence.document_id = document_id;
  occurrence.occurrence_path = occurrence_path;
  occurrence.tree_path = tree_path;
  occurrence.source_index = source_index;
  occurrence.container_index = container_index;
  occurrence.occurrence_role = occurrence_role;
  occurrence.enumeration_source = enumeration_source;
  occurrence.presentation_status = presentation_status;
  occurrence.occurrence_kind = "native_feature";
  occurrence.capture_status = "available";
  return occurrence;
}

class PartDefinitionCrawler
{
public:
  PartDefinitionCrawler(ReconstructionPackage& package,
                        CaptureIdRegistry& ids,
                        PartDefinition& definition,
                        const std::string& document_id,
                        bool register_native_objects)
    : _package(package), _ids(ids), _definition(definition), _document_id(document_id),
      _register_native_objects(register_native_objects), _next_template_index(1)
  {
  }

  bool Visit(CATISpecObject* spec,
             const std::string& parent_template_id,
             const std::string& parent_tree_path,
             const std::string& parent_occurrence_path,
             long source_index,
             long container_index,
             const std::string& occurrence_role,
             const std::string& enumeration_source,
             const std::string& presentation_status,
             std::string& error)
  {
    (void)error;
    if (!spec)
      return true;

    std::string object_id;
    std::map<CATISpecObject*, std::string>::iterator found = _entity_ids.find(spec);
    if (found == _entity_ids.end())
    {
      ObjectEntity object;
      object.object_id = _ids.NextObjectId();
      object.document_id = _document_id;
      object.object_kind = "catia_spec_object";
      object.display_name = SafeSpecString(spec, "display");
      object.internal_name = SafeSpecString(spec, "internal");
      object.startup_type = SafeSpecString(spec, "startup");
      object.update_status = SafeUpdateStatus(spec);
      object.capture_status = "available";
      object.identity.capture_id = object.object_id;
      object.identity.identity_method = "session_object_equivalence";
      object.identity.native_label = object.display_name.empty() ? object.internal_name : object.display_name;
      object.identity.scope = IdentitySessionLocal;
      object.identity.read_status = "session_local_only";
      object_id = object.object_id;
      _entity_ids[spec] = object_id;
      _package.objects.push_back(object);
      if (_register_native_objects)
      {
        NativeObjectBinding binding;
        binding.object_id = object_id;
        binding.native_spec_object = spec;
        _package.native_object_bindings.push_back(binding);
      }
    }
    else
    {
      object_id = found->second;
    }

    ObjectEntity* entity = FindEntity(object_id);
    if (entity && entity->supplemental_sources.find(enumeration_source) == std::string::npos)
    {
      if (!entity->supplemental_sources.empty())
        entity->supplemental_sources += ";";
      entity->supplemental_sources += enumeration_source;
    }

    const std::string segment = DisplaySegment(spec);
    const long display_order = FeaturePropertyChildOrder(parent_tree_path, segment);
    const long occurrence_index = display_order > 0 ? display_order : source_index;
    const std::string base_tree_path = JoinDisplayPath(parent_tree_path, segment);
    std::string tree_path = base_tree_path;
    if (occurrence_role == "primary_tree")
    {
      long count = ++_primary_tree_path_counts[base_tree_path];
      if (count > 1)
      {
        std::ostringstream disambiguated;
        disambiguated << base_tree_path << "[" << count << "]";
        tree_path = disambiguated.str();
      }
    }
    const std::string occurrence_path = JoinMachinePath(parent_occurrence_path, occurrence_index, segment);
    const std::string template_id = NextTemplateId();
    _definition.occurrence_templates.push_back(MakeTemplateOccurrence(template_id, object_id, parent_template_id,
                                                                      _document_id, tree_path, occurrence_path,
                                                                      occurrence_index, container_index,
                                                                      occurrence_role, enumeration_source,
                                                                      presentation_status));
    if (presentation_status == "visible")
      _primary_occurrence_by_entity[object_id] = template_id;

    if (_active_path.find(spec) != _active_path.end())
    {
      _package.diagnostics.push_back(MakeDiagnostic("warning", "catpart_tree_cycle", object_id,
                                                    "CATISpecObject appeared again in the active recursion path; subtree expansion stopped for this occurrence",
                                                    "part_enumerator"));
      return true;
    }

    _active_path.insert(spec);
    try
    {
      CATListValCATISpecObject_var* children = spec->ListComponents();
      if (children)
      {
        SpecListGuard children_guard(children);
        int index = 0;
        for (index = 1; index <= children->Size(); ++index)
        {
          CATISpecObject_var child = (*children)[index];
          if (child != NULL_var)
          {
            CATISpecObject* child_pointer = child;
            Visit(child_pointer, template_id, tree_path, occurrence_path, index, container_index,
                  "primary_tree", "CATISpecObject.ListComponents", "visible", error);
          }
        }
      }
    }
    catch (...)
    {
      _package.diagnostics.push_back(MakeDiagnostic("warning", "object_traversal_failed", object_id,
                                                    "CATISpecObject::ListComponents failed; scan continued",
                                                    "part_enumerator"));
    }
    _active_path.erase(spec);
    return true;
  }

  bool HasPrimaryOccurrence(CATISpecObject* spec) const
  {
    std::map<CATISpecObject*, std::string>::const_iterator found = _entity_ids.find(spec);
    if (found == _entity_ids.end())
      return false;
    return _primary_occurrence_by_entity.find(found->second) != _primary_occurrence_by_entity.end();
  }

  void NoteSupplementalSeen(CATISpecObject* spec)
  {
    std::map<CATISpecObject*, std::string>::const_iterator found = _entity_ids.find(spec);
    if (found == _entity_ids.end())
      return;
    ObjectEntity* entity = FindEntity(found->second);
    if (entity && entity->supplemental_sources.find("CATIContainer.ListMembersHere") == std::string::npos)
    {
      if (!entity->supplemental_sources.empty())
        entity->supplemental_sources += ";";
      entity->supplemental_sources += "CATIContainer.ListMembersHere";
    }
    _package.diagnostics.push_back(MakeDiagnostic("info", "supplemental_object_already_primary", found->second,
                                                  "CATIContainer::ListMembersHere found an object already present in the primary tree",
                                                  "part_enumerator"));
  }

  bool ResolvePrimaryParentByFather(CATISpecObject* spec,
                                    std::string& parent_template_id,
                                    std::string& parent_tree_path,
                                    std::string& parent_occurrence_path,
                                    long& container_index,
                                    std::string& status) const
  {
    parent_template_id.clear();
    parent_tree_path.clear();
    parent_occurrence_path.clear();
    container_index = 2;
    status = "not_found";
    CATISpecObject* current = spec;
    std::vector<CATISpecObject*> owned_fathers;
    int depth = 0;
    for (depth = 0; current && depth < 16; ++depth)
    {
      CATISpecObject* father = 0;
      try
      {
        father = current->GetFather();
      }
      catch (...)
      {
        ReleaseSpecList(owned_fathers);
        status = "father_exception";
        return false;
      }
      if (!father)
      {
        ReleaseSpecList(owned_fathers);
        status = "no_father";
        return false;
      }
      owned_fathers.push_back(father);
      std::map<CATISpecObject*, std::string>::const_iterator entity_found = _entity_ids.find(father);
      if (entity_found != _entity_ids.end())
      {
        std::map<std::string, std::string>::const_iterator occurrence_found =
          _primary_occurrence_by_entity.find(entity_found->second);
        if (occurrence_found != _primary_occurrence_by_entity.end())
        {
          const ObjectOccurrence* occurrence = FindTemplateOccurrence(occurrence_found->second);
          if (occurrence)
          {
            parent_template_id = occurrence->occurrence_id;
            parent_tree_path = occurrence->tree_path;
            parent_occurrence_path = occurrence->occurrence_path;
            container_index = occurrence->container_index;
            status = "resolved";
            ReleaseSpecList(owned_fathers);
            return true;
          }
        }
      }
      current = father;
    }
    ReleaseSpecList(owned_fathers);
    status = "depth_limit";
    return false;
  }

private:
  std::string NextTemplateId()
  {
    std::ostringstream out;
    out << "template_occurrence_" << _next_template_index++;
    return out.str();
  }

  ObjectEntity* FindEntity(const std::string& object_id)
  {
    size_t i;
    for (i = 0; i < _package.objects.size(); ++i)
    {
      if (_package.objects[i].object_id == object_id)
        return &_package.objects[i];
    }
    return 0;
  }

  const ObjectOccurrence* FindTemplateOccurrence(const std::string& occurrence_id) const
  {
    size_t i;
    for (i = 0; i < _definition.occurrence_templates.size(); ++i)
    {
      if (_definition.occurrence_templates[i].occurrence_id == occurrence_id)
        return &_definition.occurrence_templates[i];
    }
    return 0;
  }

  ReconstructionPackage& _package;
  CaptureIdRegistry& _ids;
  PartDefinition& _definition;
  std::string _document_id;
  bool _register_native_objects;
  long _next_template_index;
  std::map<CATISpecObject*, std::string> _entity_ids;
  std::map<std::string, std::string> _primary_occurrence_by_entity;
  std::map<std::string, long> _primary_tree_path_counts;
  std::set<CATISpecObject*> _active_path;
};

static std::string RootDocumentId(const ReconstructionPackage& package)
{
  if (package.document_graph.documents.empty())
    return "";
  return package.document_graph.documents[0].document_id;
}

bool CaaPartEnumerator::CaptureDefinition(CaaDocumentHandle& document_handle,
                                          CaptureIdRegistry& ids,
                                          PartDefinition& definition,
                                          ReconstructionPackage& package,
                                          std::string& error,
                                          bool register_native_objects)
{
  const std::string document_id = RootDocumentId(package);
  if (definition.document_id.empty())
    definition.document_id = document_id;
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

  ObjectEntity document_object = MakeStaticObject(ids, definition.document_id, "catia_document",
                                                  document_handle.DisplayName(), "CATDocument", "CATDocument");
  package.objects.push_back(document_object);
  ObjectEntity container_object = MakeStaticObject(ids, definition.document_id, "catia_container",
                                                   "PartSpecContainer", "CATIPrtContainer", "CATIPrtContainer");
  package.objects.push_back(container_object);

  definition.occurrence_templates.push_back(MakeTemplateOccurrence("template_document", document_object.object_id, "",
                                                                   definition.document_id, "/document", "/0:document",
                                                                   0, 0, "primary_tree", "definition.static", "visible"));
  definition.occurrence_templates.push_back(MakeTemplateOccurrence("template_container", container_object.object_id,
                                                                   "template_document", definition.document_id,
                                                                   "/document/PartSpecContainer",
                                                                   "/0:document/1:PartSpecContainer",
                                                                   1, 1, "primary_tree", "definition.static", "visible"));

  PartDefinitionCrawler crawler(package, ids, definition, definition.document_id, register_native_objects);
  CATISpecObject_var part = NULL_var;
  try
  {
    part = part_container->GetPart();
  }
  catch (...)
  {
    package.diagnostics.push_back(MakeDiagnostic("warning", "part_entry_exception", definition.document_id,
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
  if (!crawler.Visit(part_pointer, "template_container",
                     "/document/PartSpecContainer",
                     "/0:document/1:PartSpecContainer",
                     1, 1,
                     "primary_tree", "CATIPrtContainer.GetPart", "visible", error))
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
          if (crawler.HasPrimaryOccurrence(member_spec))
          {
            crawler.NoteSupplementalSeen(member_spec);
          }
          else
          {
            std::string parent_template_id;
            std::string parent_tree_path;
            std::string parent_occurrence_path;
            std::string parent_resolution_status;
            long parent_container_index = 2;
            if (crawler.ResolvePrimaryParentByFather(member_spec,
                                                     parent_template_id,
                                                     parent_tree_path,
                                                     parent_occurrence_path,
                                                     parent_container_index,
                                                     parent_resolution_status))
            {
              crawler.Visit(member_spec, parent_template_id,
                            parent_tree_path,
                            parent_occurrence_path,
                            static_cast<long>(index + 1), parent_container_index,
                            "supplemental_discovery",
                            "CATIContainer.ListMembersHere.GetFather",
                            "visible",
                            error);
            }
            else
            {
              package.diagnostics.push_back(MakeDiagnostic("info", "supplemental_parent_unresolved",
                                                           definition.document_id,
                                                           "CATIContainer::ListMembersHere returned an object whose CATISpecObject::GetFather chain did not reach the primary tree: " +
                                                           parent_resolution_status,
                                                           "part_enumerator"));
              crawler.Visit(member_spec, "template_container",
                            "/document/PartSpecContainer",
                            "/0:document/1:PartSpecContainer",
                            static_cast<long>(index + 1), 2,
                            "supplemental_discovery",
                            "CATIContainer.ListMembersHere",
                            "non_primary",
                            error);
            }
          }
        }
      }
    }
    catch (...)
    {
      package.diagnostics.push_back(MakeDiagnostic("warning", "container_enumeration_exception", definition.document_id,
                                                   "CATIContainer::ListMembersHere failed; scan continued",
                                                   "part_enumerator"));
    }
  }
  else
  {
    package.diagnostics.push_back(MakeDiagnostic("info", "applicative_container_unavailable", definition.document_id,
                                                 "root container does not expose CATIContainer",
                                                 "part_enumerator"));
  }

  package.diagnostics.push_back(MakeDiagnostic("info", "catpart_definition_captured", definition.document_id,
                                               "CATPart definition tree captured once from native CATDocument",
                                               "part_enumerator"));
  return true;
}

bool CaaPartEnumerator::ProjectDefinition(const PartDefinition& definition,
                                          const ProjectionContext& context,
                                          CaptureIdRegistry& ids,
                                          ReconstructionPackage& package,
                                          std::string& error)
{
  (void)error;
  std::map<std::string, std::string> occurrence_id_by_template;
  size_t i;
  for (i = 0; i < definition.occurrence_templates.size(); ++i)
  {
    const ObjectOccurrence& source = definition.occurrence_templates[i];
    ObjectOccurrence projected = source;
    projected.occurrence_id = ids.NextOccurrenceId();
    occurrence_id_by_template[source.occurrence_id] = projected.occurrence_id;
    if (source.parent_occurrence_id.empty())
      projected.parent_occurrence_id = context.parent_occurrence_id;
    else
      projected.parent_occurrence_id = occurrence_id_by_template[source.parent_occurrence_id];

    projected.product_occurrence_id = context.product_occurrence_id;
    projected.reference_id = context.reference_id;
    projected.referenced_document_id = context.referenced_document_id.empty() ? definition.document_id : context.referenced_document_id;

    if (!context.tree_path_prefix.empty())
      projected.tree_path = context.tree_path_prefix + source.tree_path;
    if (!context.occurrence_path_prefix.empty())
      projected.occurrence_path = context.occurrence_path_prefix + source.occurrence_path;

    package.occurrence_graph.object_occurrences.push_back(projected);
  }
  return true;
}

bool CaaPartEnumerator::Enumerate(CaaDocumentHandle& document_handle,
                                  CaptureIdRegistry& ids,
                                  ReconstructionPackage& package,
                                  std::string& error)
{
  if (package.document_graph.documents.empty() ||
      package.document_graph.documents[0].document_kind != "catpart")
  {
    return true;
  }

  PartDefinition definition;
  if (!CaptureDefinition(document_handle, ids, definition, package, error, true))
    return false;

  ProjectionContext context;
  context.referenced_document_id = definition.document_id;
  if (!ProjectDefinition(definition, context, ids, package, error))
    return false;

  package.diagnostics.push_back(MakeDiagnostic("info", "catpart_tree_captured", definition.document_id,
                                               "CATPart specification tree projected from captured definition",
                                               "part_enumerator"));
  return true;
}

}
