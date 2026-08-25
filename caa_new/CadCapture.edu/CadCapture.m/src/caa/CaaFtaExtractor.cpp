#include "caa/CaaFtaExtractor.h"
#include "caa/CaaGuards.h"

#include <CATDocument.h>
#include <CATITPSComponent.h>
#include <CATITPSDocument.h>
#include <CATITPSGeometryList.h>
#include <CATITPSList.h>
#include <CATITPSSet.h>
#include <sstream>

namespace cadcapture {

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
                          const char* diagnostic_message)
{
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

  const long set_count = SafeListCount(sets, package, document_id,
                                       "tps_set_count_failed",
                                       "CATITPSList::Count failed for TPS set list");
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
  return true;
}

}
