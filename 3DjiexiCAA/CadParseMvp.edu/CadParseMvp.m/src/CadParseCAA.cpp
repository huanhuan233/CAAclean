#include "CadParseCAA.h"

#include "CATBaseUnknown.h"
#include "CATDocument.h"
#include "CATDocumentServices.h"
#include "CATIContainer.h"
#include "CATInit.h"
#include "CATIPrtContainer.h"
#include "CATIPrtPart.h"
#include "CATISpecObject.h"
#include "CATLISTV_CATISpecObject.h"
#include "CATSession.h"
#include "CATSessionServices.h"
#include "CATUnicodeString.h"

#include <algorithm>
#include <cstring>
#include <sys/stat.h>
#include <vector>

namespace cadparse
{
template <class T>
class CaaInterfaceGuard
{
public:
  explicit CaaInterfaceGuard(T* pointer = 0) : _pointer(pointer) {}
  ~CaaInterfaceGuard() { if (_pointer) _pointer->Release(); }
  T* Get() const { return _pointer; }

private:
  CaaInterfaceGuard(const CaaInterfaceGuard&);
  CaaInterfaceGuard& operator=(const CaaInterfaceGuard&);
  T* _pointer;
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
  explicit BaseUnknownSequenceGuard(SEQUENCE(CATBaseUnknown_ptr)& sequence)
    : _sequence(sequence) {}
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

std::string UnicodeToUtf8(const CATUnicodeString& value)
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

SessionGuard::SessionGuard() : _open(false), _name("CadParseMvpSession") {}

SessionGuard::~SessionGuard()
{
  if (_open)
    Delete_Session(const_cast<char*>(_name.c_str()));
}

bool SessionGuard::Open(std::string& error)
{
  CATSession* session = 0;
  const HRESULT result = Create_Session(const_cast<char*>(_name.c_str()), session);
  if (FAILED(result) || !session)
  {
    error = "CAA session initialization failed";
    return false;
  }
  _open = true;
  return true;
}

DocumentGuard::DocumentGuard() : _document(0) {}

DocumentGuard::~DocumentGuard()
{
  if (_document)
  {
    CATDocumentServices::Remove(*_document);
    _document = 0;
  }
}

static bool EndsWithCatPart(const std::string& path)
{
  if (path.size() < 8) return false;
  std::string suffix = path.substr(path.size() - 8);
  std::transform(suffix.begin(), suffix.end(), suffix.begin(), ::tolower);
  return suffix == ".catpart";
}

bool DocumentGuard::OpenReadOnly(const std::string& path, std::string& error)
{
  struct _stat file_status;
  if (_stat(path.c_str(), &file_status) != 0)
  {
    error = "input file does not exist";
    return false;
  }
  if (!EndsWithCatPart(path))
  {
    error = "input file is not a CATPart";
    return false;
  }
  const CATUnicodeString storage_name(path.c_str());
  const HRESULT result = CATDocumentServices::OpenDocument(storage_name, _document, TRUE);
  if (FAILED(result) || !_document)
  {
    error = "CATPart open failed";
    return false;
  }
  return true;
}

CATDocument* DocumentGuard::Get() const { return _document; }

class StaticObjectView : public INativeObjectView
{
public:
  StaticObjectView(const char* native_type, const char* kind, const std::string& name)
  {
    _fingerprint.native_type = native_type;
    _fingerprint.container_kind = kind;
    _fingerprint.internal_name = name;
    _fingerprint.display_name = name;
  }

  const TypeFingerprint& GetFingerprint() const { return _fingerprint; }

  bool ReadBasicAttributes(FeatureRecord& output, std::string&) const
  {
    output.attributes["object_kind"] = _fingerprint.container_kind;
    return true;
  }

private:
  TypeFingerprint _fingerprint;
};

class SpecObjectView : public INativeObjectView
{
public:
  SpecObjectView(CATISpecObject* spec, ParseContext& context) : _spec(spec)
  {
    BuildFingerprint(context);
  }

  const TypeFingerprint& GetFingerprint() const { return _fingerprint; }

  bool ReadBasicAttributes(FeatureRecord& output, std::string& error) const
  {
    if (!_spec)
    {
      error = "null CATISpecObject";
      return false;
    }
    try
    {
      output.update_status = _spec->IsUpToDate() ? "up_to_date" : "not_up_to_date";
      const CATIContainer_var container = _spec->GetFeatContainer();
      output.attributes["container_accessible"] = container == NULL_var ? "false" : "true";
      output.attributes["result_summary"] = "not_exposed_by_verified_mvp_interface";
      return true;
    }
    catch (...)
    {
      error = "CATISpecObject basic attribute read failed";
      return false;
    }
  }

private:
  class R21InterfaceProbeService : public InterfaceProbeService
  {
  public:
    explicit R21InterfaceProbeService(CATISpecObject* spec) : _spec(spec) {}

    bool Probe(const char* key, TypeFingerprint& fingerprint, ParseStatistics& statistics)
    {
      if (std::strcmp(key, "CATISpecObject") == 0)
      {
        fingerprint.supported_interface_keys.push_back(key);
        ++statistics.interface_probe_success_count;
        return true;
      }
      const IID* iid = 0;
      if (std::strcmp(key, "CATIPrtPart") == 0) iid = &IID_CATIPrtPart;
      else if (std::strcmp(key, "CATIContainer") == 0) iid = &IID_CATIContainer;
      else if (std::strcmp(key, "CATIPrtContainer") == 0) iid = &IID_CATIPrtContainer;
      if (!iid)
      {
        ++statistics.interface_probe_failure_count;
        return false;
      }
      void* result = 0;
      if (SUCCEEDED(_spec->QueryInterface(*iid, &result)) && result)
      {
        fingerprint.supported_interface_keys.push_back(key);
        static_cast<CATBaseUnknown*>(result)->Release();
        ++statistics.interface_probe_success_count;
        return true;
      }
      ++statistics.interface_probe_failure_count;
      return false;
    }

  private:
    CATISpecObject* _spec;
  };

  void BuildFingerprint(ParseContext& context)
  {
    if (!_spec) return;
    // TODO(R21_API_VERIFY): no documented Public R21 native runtime type getter was confirmed.
    try
    {
      _fingerprint.startup_type = UnicodeToUtf8(_spec->GetType());
      const std::string super_type = UnicodeToUtf8(_spec->GetSuperType());
      if (!super_type.empty()) _fingerprint.super_types.push_back(super_type);
      _fingerprint.internal_name = UnicodeToUtf8(_spec->GetName());
      _fingerprint.display_name = UnicodeToUtf8(_spec->GetDisplayName());
      _fingerprint.container_kind = "feature";
    }
    catch (...)
    {
      context.AddDiagnostic("warning", "fingerprint", "SPEC_FINGERPRINT_READ_FAILED",
                            "one or more CATISpecObject type fields were unavailable", "");
    }
    R21InterfaceProbeService probes(_spec);
    probes.Probe("CATISpecObject", _fingerprint, context.statistics);
    probes.Probe("CATIPrtPart", _fingerprint, context.statistics);
    probes.Probe("CATIContainer", _fingerprint, context.statistics);
    probes.Probe("CATIPrtContainer", _fingerprint, context.statistics);
    if (std::find(_fingerprint.supported_interface_keys.begin(),
                  _fingerprint.supported_interface_keys.end(), "CATIPrtPart") !=
        _fingerprint.supported_interface_keys.end())
      _fingerprint.container_kind = "part";
  }

  CATISpecObject* _spec;
  TypeFingerprint _fingerprint;
};

class CoreDecoder : public IFeatureDecoder
{
public:
  CoreDecoder(const char* id, int priority) : _id(id), _priority(priority) {}
  const char* GetDecoderId() const { return _id; }
  int GetPriority() const { return _priority; }
  DecodeResult Decode(const INativeObjectView& view, ParseContext& context, FeatureRecord& output)
  {
    std::string error;
    if (!view.ReadBasicAttributes(output, error))
      return DecodeResult(false, "failed", error.c_str());
    output.decoder_id = _id;
    output.decode_level = "typed";
    output.decode_status = "success";
    return DecodeResult(true, "typed");
  }

protected:
  const char* _id;
  int _priority;
};

class DocumentDecoder : public CoreDecoder
{
public:
  DocumentDecoder() : CoreDecoder("document", 400) {}
  bool Match(const TypeFingerprint& fp, const INativeObjectView&) const
  { return fp.container_kind == "document"; }
};

class PartDecoder : public CoreDecoder
{
public:
  PartDecoder() : CoreDecoder("part", 700) {}
  bool Match(const TypeFingerprint& fp, const INativeObjectView&) const
  { return std::find(fp.supported_interface_keys.begin(), fp.supported_interface_keys.end(),
                     "CATIPrtPart") != fp.supported_interface_keys.end(); }
};

class ContainerDecoder : public CoreDecoder
{
public:
  ContainerDecoder() : CoreDecoder("container", 350) {}
  bool Match(const TypeFingerprint& fp, const INativeObjectView&) const
  { return fp.container_kind == "container"; }
};

class BodyDecoder : public CoreDecoder
{
public:
  BodyDecoder() : CoreDecoder("body", 500) {}
  // TODO(R21_API_VERIFY): installed PublicInterfaces contain no CATIBody marker interface.
  bool Match(const TypeFingerprint& fp, const INativeObjectView&) const
  { return fp.startup_type == "Body" || fp.startup_type == "MechanicalTool"; }
};

class HybridBodyDecoder : public CoreDecoder
{
public:
  HybridBodyDecoder() : CoreDecoder("hybrid_body", 500) {}
  // TODO(R21_API_VERIFY): installed PublicInterfaces contain no CATIHybridBody marker interface.
  bool Match(const TypeFingerprint& fp, const INativeObjectView&) const
  { return fp.startup_type == "HybridBody" || fp.startup_type == "GeometricalSet"; }
};

void RegisterCoreDecoders(FeatureTypeRegistry& registry,
                          std::vector<IFeatureDecoder*>& owned_decoders)
{
  owned_decoders.push_back(new DocumentDecoder());
  owned_decoders.push_back(new PartDecoder());
  owned_decoders.push_back(new ContainerDecoder());
  owned_decoders.push_back(new BodyDecoder());
  owned_decoders.push_back(new HybridBodyDecoder());
  std::vector<IFeatureDecoder*>::iterator it = owned_decoders.begin();
  for (; it != owned_decoders.end(); ++it) registry.Register(*it);
}

void DeleteCoreDecoders(std::vector<IFeatureDecoder*>& owned_decoders)
{
  std::vector<IFeatureDecoder*>::iterator it = owned_decoders.begin();
  for (; it != owned_decoders.end(); ++it) delete *it;
  owned_decoders.clear();
}

UniversalFeatureCrawler::UniversalFeatureCrawler(FeatureTypeRegistry& registry, ParseContext& context,
                                                 std::vector<FeatureRecord>& features,
                                                 std::vector<RelationRecord>& relations)
  : _registry(registry), _context(context), _features(features), _relations(relations)
{
}

std::string UniversalFeatureCrawler::AddObject(INativeObjectView& view,
                                               const std::string& parent_id,
                                               const std::string& tree_path)
{
  FeatureRecord record;
  record.feature_id = _ids.Next();
  record.parent_id = parent_id;
  record.traversal_index = static_cast<long>(_features.size() + 1);
  record.tree_path = tree_path;
  record.update_status = "unknown";
  record.visibility = "unknown";
  _catalog.Observe(view.GetFingerprint());
  _registry.DecodeObject(view, _context, record);
  _features.push_back(record);
  if (!parent_id.empty())
  {
    RelationRecord relation;
    relation.kind = "parent_of";
    relation.from_id = parent_id;
    relation.to_id = record.feature_id;
    _relations.push_back(relation);
    relation.kind = "contains";
    _relations.push_back(relation);
  }
  return record.feature_id;
}

struct ChildEntry
{
  std::string key;
  CATISpecObject_var object;
};

static bool ChildLess(const ChildEntry& left, const ChildEntry& right)
{
  return left.key < right.key;
}

static std::string BuildSpecSortKey(CATISpecObject* object)
{
  if (!object) return "unknown";
  try
  {
    return UnicodeToUtf8(object->GetType()) + "\x1f" +
           UnicodeToUtf8(object->GetDisplayName()) + "\x1f" +
           UnicodeToUtf8(object->GetName());
  }
  catch (...) { return "unknown"; }
}

static void DiagnoseEqualKeys(const std::vector<ChildEntry>& ordered, ParseContext& context,
                              const std::string& feature_id)
{
  size_t index = 1;
  for (; index < ordered.size(); ++index)
  {
    if (ordered[index - 1].key == ordered[index].key)
    {
      context.AddDiagnostic("warning", "discovery", "NON_UNIQUE_TRAVERSAL_KEY",
                            "equal R21 public sort keys; order within this group is not guaranteed",
                            feature_id);
      return;
    }
  }
}

bool UniversalFeatureCrawler::VisitSpec(CATISpecObject* spec, const std::string& parent_id,
                                        const std::string& parent_path)
{
  if (!spec || _visited.find(spec) != _visited.end()) return true;
  _visited.insert(spec);

  try
  {
    SpecObjectView view(spec, _context);
    const TypeFingerprint& fp = view.GetFingerprint();
    _unknown_types.Observe(fp);
    _context.statistics.unknown_native_type_count = static_cast<long>(_unknown_types.Count());
    std::string segment = fp.display_name.empty() ? fp.internal_name : fp.display_name;
    if (segment.empty()) segment = fp.startup_type.empty() ? "unnamed" : fp.startup_type;
    const std::string path = parent_path + "/" + segment;
    const std::string id = AddObject(view, parent_id, path);

    CATListValCATISpecObject_var* children = spec->ListComponents();
    if (!children) return true;
    SpecListGuard children_guard(children);
    std::vector<ChildEntry> ordered;
    int index = 0;
    for (index = 1; index <= children->Size(); ++index)
    {
      ChildEntry entry;
      entry.object = (*children)[index];
      if (entry.object != NULL_var)
      {
        CATISpecObject* entry_pointer = entry.object;
        entry.key = BuildSpecSortKey(entry_pointer);
        ordered.push_back(entry);
      }
    }
    std::stable_sort(ordered.begin(), ordered.end(), ChildLess);
    DiagnoseEqualKeys(ordered, _context, id);
    std::vector<ChildEntry>::iterator child = ordered.begin();
    for (; child != ordered.end(); ++child)
    {
      CATISpecObject* child_pointer = child->object;
      VisitSpec(child_pointer, id, path);
    }
    return true;
  }
  catch (...)
  {
    _context.AddDiagnostic("warning", "discovery", "OBJECT_TRAVERSAL_FAILED",
                           "CATISpecObject traversal failed; scan continued", parent_id);
    return false;
  }
}

bool UniversalFeatureCrawler::Crawl(CATDocument* document, std::string& error)
{
  if (!document)
  {
    error = "null CATDocument";
    return false;
  }
  try
  {
  StaticObjectView document_view("CATDocument", "document", UnicodeToUtf8(document->DisplayName()));
  const std::string document_id = AddObject(document_view, "", "/document");

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
  const HRESULT root_result = root->QueryInterface(IID_CATIPrtContainer,
                                                    reinterpret_cast<void**>(&part_container));
  if (FAILED(root_result) || !part_container)
  {
    error = "CATIPrtContainer query failed";
    return false;
  }
  CaaInterfaceGuard<CATIPrtContainer> part_container_guard(part_container);

  StaticObjectView container_view("CATIPrtContainer", "container", "PartSpecContainer");
  const std::string container_id = AddObject(container_view, document_id, "/document/PartSpecContainer");
  ++_context.statistics.container_count;

  CATISpecObject_var part = NULL_var;
  try
  {
    part = part_container->GetPart();
  }
  catch (...)
  {
    _context.AddDiagnostic("warning", "discovery", "PART_ENTRY_EXCEPTION",
                           "CATIPrtContainer::GetPart raised an exception", container_id);
    error = "Part root access failed";
    return false;
  }
  if (part != NULL_var)
  {
    CATISpecObject* part_pointer = part;
    if (!VisitSpec(part_pointer, container_id, "/document/PartSpecContainer"))
    {
      error = "Part root traversal failed";
      return false;
    }
  }
  else
  {
    _context.AddDiagnostic("warning", "discovery", "PART_ENTRY_UNAVAILABLE",
                           "CATIPrtContainer::GetPart returned null", container_id);
    error = "Part root is unavailable";
    return false;
  }

  CATIContainer* generic_container = 0;
  if (SUCCEEDED(root->QueryInterface(IID_CATIContainer,
                                     reinterpret_cast<void**>(&generic_container))) && generic_container)
  {
    CaaInterfaceGuard<CATIContainer> generic_container_guard(generic_container);
    try
    {
      SEQUENCE(CATBaseUnknown_ptr) members;
      BaseUnknownSequenceGuard members_guard(members);
      const CATLONG32 count = generic_container->ListMembersHere("CATISpecObject", members);
      std::vector<ChildEntry> ordered_members;
      CATLONG32 index = 0;
      for (index = 0; index < count; ++index)
      {
        CATBaseUnknown* member = members[index];
        if (!member) continue;
        CATISpecObject* member_spec = 0;
        if (SUCCEEDED(member->QueryInterface(IID_CATISpecObject,
                                             reinterpret_cast<void**>(&member_spec))) && member_spec)
        {
          CaaInterfaceGuard<CATISpecObject> member_spec_guard(member_spec);
          ChildEntry entry;
          entry.object = member_spec;
          entry.key = BuildSpecSortKey(member_spec);
          ordered_members.push_back(entry);
        }
      }
      std::stable_sort(ordered_members.begin(), ordered_members.end(), ChildLess);
      DiagnoseEqualKeys(ordered_members, _context, container_id);
      std::vector<ChildEntry>::iterator member_entry = ordered_members.begin();
      for (; member_entry != ordered_members.end(); ++member_entry)
      {
        CATISpecObject* member_pointer = member_entry->object;
        VisitSpec(member_pointer, container_id, "/document/PartSpecContainer");
      }
    }
    catch (...)
    {
      _context.AddDiagnostic("warning", "discovery", "CONTAINER_ENUMERATION_EXCEPTION",
                             "CATIContainer member enumeration failed", container_id);
      error = "supplemental container enumeration failed";
      return false;
    }
  }
  else
    _context.AddDiagnostic("info", "discovery", "APPLICATIVE_CONTAINER_UNAVAILABLE",
                           "root container does not expose CATIContainer", container_id);

  _context.statistics.relation_count = static_cast<long>(_relations.size());
  return true;
  }
  catch (...)
  {
    error = "CAA traversal raised an unhandled exception";
    return false;
  }
}
}
