#include "caa/CaaFtaExtractor.h"
#include "caa/CaaGuards.h"
#include "caa/CaaPropertyEvidence.h"

#include <CATDocument.h>
#include <CATITPSComponent.h>
#include <CATITPS.h>
#include <CATITPSDocument.h>
#include <CATITPSGeometryList.h>
#include <CATITPSList.h>
#include <CATITPSSemanticValidity.h>
#include <CATITPSSet.h>
#include <CATITPSText.h>
#include <CATITPSFlagNote.h>
#include <CATITPSNoa.h>
#include <CATITPSTextContent.h>
#include <CATUnicodeString.h>
#include <CATTPSStatus.h>
#include <sstream>
#include <vector>

namespace cadcapture {

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

static std::string RootDocumentSubject(const ReconstructionPackage& package)
{
  if (!package.document_graph.documents.empty())
    return package.document_graph.documents[0].document_id;
  return "document";
}

static long SafeListCount(CATITPSList* list,
                          ReconstructionPackage& package,
                          const std::string& subject_id,
                          const char* diagnostic_code,
                          const char* diagnostic_message,
                          bool* read_succeeded = 0)
{
  if (read_succeeded) *read_succeeded = false;
  if (!list)
    return 0;
  unsigned int count = 0;
  try
  {
    if (FAILED(list->Count(&count)))
    {
      package.diagnostics.push_back(MakeDiagnostic("warning", diagnostic_code, subject_id,
                                                   diagnostic_message, "fta_extractor"));
      return 0;
    }
  }
  catch (...)
  {
    package.diagnostics.push_back(MakeDiagnostic("warning", diagnostic_code, subject_id,
                                                 diagnostic_message, "fta_extractor"));
    return 0;
  }
  if (read_succeeded) *read_succeeded = true;
  return static_cast<long>(count);
}

static long SafeGeometryListCount(CATITPSGeometryList* list,
                                  ReconstructionPackage& package,
                                  const std::string& subject_id)
{
  if (!list)
    return 0;
  unsigned int count = 0;
  try
  {
    if (FAILED(list->Count(&count)))
    {
      package.diagnostics.push_back(MakeDiagnostic("warning", "tps_set_geometry_count_failed",
                                                   subject_id,
                                                   "CATITPSGeometryList::Count failed",
                                                   "fta_extractor"));
      return 0;
    }
  }
  catch (...)
  {
    package.diagnostics.push_back(MakeDiagnostic("warning", "tps_set_geometry_count_exception",
                                                 subject_id,
                                                 "CATITPSGeometryList::Count raised an exception",
                                                 "fta_extractor"));
    return 0;
  }
  return static_cast<long>(count);
}

static std::string SemanticId(const std::string& set_id, long one_based_index)
{
  std::ostringstream out;
  out << set_id << "_TPS";
  if (one_based_index < 10) out << "00000";
  else if (one_based_index < 100) out << "0000";
  else if (one_based_index < 1000) out << "000";
  else if (one_based_index < 10000) out << "00";
  else if (one_based_index < 100000) out << "0";
  out << one_based_index;
  return out.str();
}

template<class T> static void ReadAnnotationText(CATITPSComponent* component, const IID& iid,
                                                 const char* interface_name, const PmiEntity& set_entity,
                                                 FtaSemanticEntity& entity, CaptureIdRegistry& ids,
                                                 ReconstructionPackage& package)
{
  CaaInterfaceGuard<T> text;
  wchar_t* native_text = 0;
  PropertyFact fact = evidence::Failure("failed", std::string(interface_name) + ".GetText");
  try
  {
    if (FAILED(component->QueryInterface(iid, reinterpret_cast<void**>(&text.Out()))) || !text.Get()) return;
    entity.supported_interface_keys.push_back(interface_name);
    if (SUCCEEDED(text.Get()->GetText(&native_text)) && native_text)
    {
      CATUnicodeString unicode;
      unicode.BuildFromWChar(native_text);
      fact = evidence::Text(UnicodeToUtf8Local(unicode), fact.source_api);
    }
  }
  catch (...) { fact.read_status = "exception"; }
  delete [] native_text;
  // 文本、校验串和诊断是三种证据，不能互相冒充；每个支持的文本接口单独留存。
  evidence::Append(ids, package, set_entity.subject_id, "annotations",
                   entity.fta_semantic_id + ":" + interface_name, "Annotation text", fact);
  if (entity.annotation_text_status != "available")
  {
    entity.annotation_text = fact.raw_value;
    entity.annotation_text_status = fact.read_status;
    entity.annotation_text_source = fact.source_api;
  }
}

static void AppendFtaSemantic(CATITPSComponent* component,
                              const PmiEntity& set_entity,
                              long component_index,
                              CaptureIdRegistry& ids,
                              ReconstructionPackage& package)
{
  FtaSemanticEntity entity;
  entity.fta_semantic_id = SemanticId(set_entity.pmi_id, component_index + 1);
  entity.fta_set_id = set_entity.pmi_id;
  entity.component_index = component_index + 1;
  entity.read_status = component ? "partial" : "unavailable";
  entity.component_kind = "unknown_tps_component";
  entity.value_source = "typed_caa_public_tps_component";
  if (!component)
  {
    package.fta_semantics.push_back(entity);
    return;
  }

  ReadAnnotationText<CATITPSText>(component, IID_CATITPSText, "CATITPSText", set_entity, entity, ids, package);
  ReadAnnotationText<CATITPSFlagNote>(component, IID_CATITPSFlagNote, "CATITPSFlagNote", set_entity, entity, ids, package);
  ReadAnnotationText<CATITPSNoa>(component, IID_CATITPSNoa, "CATITPSNoa", set_entity, entity, ids, package);

  try
  {
  CATITPS* tps = 0;
  if (SUCCEEDED(component->QueryInterface(IID_CATITPS, reinterpret_cast<void**>(&tps))) && tps)
  {
    CaaInterfaceGuard<CATITPS> tps_guard(tps);
    entity.supported_interface_keys.push_back("CATITPS");
    entity.component_kind = "tps";
  }

  CATITPSSemanticValidity* semantic = 0;
  if (SUCCEEDED(component->QueryInterface(IID_CATITPSSemanticValidity,
                                          reinterpret_cast<void**>(&semantic))) && semantic)
  {
    CaaInterfaceGuard<CATITPSSemanticValidity> semantic_guard(semantic);
    entity.supported_interface_keys.push_back("CATITPSSemanticValidity");
    int count = 0;
    IID** iid_list = 0;
    if (SUCCEEDED(semantic->GetUnderstandingSemanticsItf(&count, &iid_list)))
    {
      entity.semantic_interface_count = static_cast<long>(count);
      delete [] iid_list;
    }
    count = 0;
    iid_list = 0;
    if (SUCCEEDED(semantic->GetAllSemanticsItf(&count, &iid_list)))
    {
      entity.all_semantic_interface_count = static_cast<long>(count);
      delete [] iid_list;
    }
    wchar_t* diagnostic = 0;
    CATTPSStatus status = CATTPSStatusUnknown;
    if (SUCCEEDED(semantic->Check(&diagnostic, &status)))
    {
      entity.semantic_check_status_raw = static_cast<long>(status);
      if (diagnostic)
      {
        CATUnicodeString diagnostic_text;
        diagnostic_text.BuildFromWChar(diagnostic);
        entity.semantic_check_diagnostic = UnicodeToUtf8Local(diagnostic_text);
        delete [] diagnostic;
      }
    }
  }

  CATITPSTextContent* text_content = 0;
  if (SUCCEEDED(component->QueryInterface(IID_CATITPSTextContent,
                                          reinterpret_cast<void**>(&text_content))) && text_content)
  {
    CaaInterfaceGuard<CATITPSTextContent> text_content_guard(text_content);
    entity.supported_interface_keys.push_back("CATITPSTextContent");
    CATUnicodeString validation_text;
    if (SUCCEEDED(text_content->GetValidationString(validation_text)))
    {
      entity.validation_text = UnicodeToUtf8Local(validation_text);
      entity.validation_text_status = "success";
    }
    else
      entity.validation_text_status = "failed";
  }

  }
  catch (...)
  {
    package.diagnostics.push_back(MakeDiagnostic("warning", "tps_semantic_probe_exception",
      entity.fta_semantic_id, "Semantic probe failed; independently captured text is retained", "fta_extractor"));
  }
  // 支持接口只证明可查询，不能据此宣称语义或拓扑已经完整。
  if (entity.annotation_text_status == "available" || entity.validation_text_status == "success")
    entity.read_status = "partial";
  else if (!entity.supported_interface_keys.empty())
    entity.read_status = "interface_only";
  package.fta_semantics.push_back(entity);
}

bool CaaFtaExtractor::Extract(CaaDocumentHandle& document_handle,
                              CaptureIdRegistry& ids,
                              CaaCapabilityBroker& broker,
                              ReconstructionPackage& package)
{
  CATDocument* document = static_cast<CATDocument*>(document_handle.NativeDocumentForCaaOnly());
  const std::string document_id = RootDocumentSubject(package);
  if (!document)
  {
    package.diagnostics.push_back(MakeDiagnostic("info", "tps_document_unavailable", document_id,
                                                 "Native CATDocument is unavailable for TPS scan",
                                                 "fta_extractor"));
    return true;
  }

  CaaCapabilityLease tps_document_lease;
  broker.Acquire<CATITPSDocument>(document, IID_CATITPSDocument,
                                  "fta.CATITPSDocument", document_id,
                                  package, tps_document_lease);
  if (!tps_document_lease.IsAvailable())
    return true;
  CATITPSDocument* tps_document = tps_document_lease.As<CATITPSDocument>();

  CATITPSList* sets = 0;
  try
  {
    // 保留递归扫描契约，覆盖子装配标注；不因增加文本读取而缩小原有采集范围。
    if (FAILED(tps_document->GetSets(&sets, CATTPSSSMRecursive, FALSE)) || !sets)
    {
      package.diagnostics.push_back(MakeDiagnostic("info", "tps_sets_empty_or_unavailable", document_id,
                                                   "CATITPSDocument::GetSets returned no set list",
                                                   "fta_extractor"));
      return true;
    }
  }
  catch (...)
  {
    package.diagnostics.push_back(MakeDiagnostic("warning", "tps_get_sets_exception", document_id,
                                                 "CATITPSDocument::GetSets raised an exception",
                                                 "fta_extractor"));
    return true;
  }
  CaaInterfaceGuard<CATITPSList> sets_guard(sets);

  bool set_count_available = false;
  const long set_count = SafeListCount(sets, package, document_id,
                                       "tps_set_count_failed",
                                       "CATITPSList::Count failed for TPS set list", &set_count_available);
  long index = 0;
  for (index = 0; index < set_count; ++index)
  {
    CATITPSComponent* component = 0;
    try
    {
      if (FAILED(sets->Item(static_cast<unsigned int>(index), &component)) || !component)
      {
        package.diagnostics.push_back(MakeDiagnostic("warning", "tps_set_item_failed",
                                                     document_id,
                                                     "CATITPSList::Item failed for a TPS set",
                                                     "fta_extractor"));
        continue;
      }
    }
    catch (...)
    {
      package.diagnostics.push_back(MakeDiagnostic("warning", "tps_set_item_exception",
                                                   document_id,
                                                   "CATITPSList::Item raised an exception for a TPS set",
                                                   "fta_extractor"));
      continue;
    }
    CaaInterfaceGuard<CATITPSComponent> component_guard(component);

    CaaCapabilityLease set_lease;
    broker.Acquire<CATITPSSet>(reinterpret_cast<CATBaseUnknown*>(component), IID_CATITPSSet,
                               "fta.CATITPSSet", document_id,
                               package, set_lease);
    if (!set_lease.IsAvailable())
      continue;
    CATITPSSet* set_interface = set_lease.As<CATITPSSet>();

    PmiEntity pmi;
    pmi.pmi_id = ids.NextPmiId();
    pmi.subject_id = document_id;
    pmi.pmi_kind = "fta_set";
    pmi.source_api = "CATITPSDocument.GetSets";
    pmi.evidence_status = "set_level_counts";
    pmi.set_index = index + 1;
    pmi.read_status = "available";

    CATITPSList* tps_list = 0;
    try
    {
      if (SUCCEEDED(set_interface->GetTPSs(&tps_list)) && tps_list)
      {
        CaaInterfaceGuard<CATITPSList> tps_list_guard(tps_list);
        pmi.tps_count = SafeListCount(tps_list, package, pmi.pmi_id,
                                      "tps_set_tps_count_failed",
                                      "CATITPSList::Count failed for TPS list");
        unsigned int tps_index = 0;
        for (; tps_index < static_cast<unsigned int>(pmi.tps_count); ++tps_index)
        {
          CATITPSComponent* tps_component = 0;
          if (SUCCEEDED(tps_list->Item(tps_index, &tps_component)) && tps_component)
          {
            CaaInterfaceGuard<CATITPSComponent> tps_component_guard(tps_component);
            try { AppendFtaSemantic(tps_component, pmi, static_cast<long>(tps_index), ids, package); }
            catch (...)
            {
              pmi.read_status = "partial";
              package.diagnostics.push_back(MakeDiagnostic("warning", "tps_component_read_exception",
                pmi.pmi_id, "Annotation read failed; remaining annotations continue", "fta_extractor"));
            }
          }
          else
          {
            package.diagnostics.push_back(MakeDiagnostic("warning", "tps_component_item_failed",
                                                         pmi.pmi_id,
                                                         "CATITPSList::Item failed for a TPS component",
                                                         "fta_extractor"));
          }
        }
      }
    }
    catch (...)
    {
      pmi.read_status = "partial";
      package.diagnostics.push_back(MakeDiagnostic("warning", "tps_set_tps_list_exception",
                                                   pmi.pmi_id,
                                                   "CATITPSSet::GetTPSs raised an exception",
                                                   "fta_extractor"));
    }

    CATITPSGeometryList* geometry_list = 0;
    try
    {
      if (SUCCEEDED(set_interface->GetGeometries(&geometry_list)) && geometry_list)
      {
        CaaInterfaceGuard<CATITPSGeometryList> geometry_guard(geometry_list);
        pmi.geometry_reference_count = SafeGeometryListCount(geometry_list, package, pmi.pmi_id);
      }
    }
    catch (...)
    {
      pmi.read_status = "partial";
      package.diagnostics.push_back(MakeDiagnostic("warning", "tps_set_geometry_list_exception",
                                                   pmi.pmi_id,
                                                   "CATITPSSet::GetGeometries raised an exception",
                                                   "fta_extractor"));
    }

    package.pmi.push_back(pmi);
  }

  package.diagnostics.push_back(MakeDiagnostic("info", "tps_set_scan_complete", document_id,
                                               "CATITPSDocument set-level scan completed",
                                               "fta_extractor"));
  const char* count_api = "CATITPSDocument.GetSets(recursive).Count";
  // Count 失败不能变成成功的零个标注，调用方必须能区分没有与未读到。
  PropertyFact count_fact = set_count_available ? evidence::Text(evidence::Number(set_count), count_api)
                                               : evidence::Failure("failed", count_api);
  count_fact.value_type = "integer";
  evidence::Append(ids, package, document_id, "annotations", "catia_fta_set_count", "FTA set count", count_fact);
  return true;
}

}
