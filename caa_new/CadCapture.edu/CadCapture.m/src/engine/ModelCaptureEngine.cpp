#include "engine/ModelCaptureEngine.h"
#include "caa/CaaCapabilityBroker.h"
#include "caa/CaaDocumentScanner.h"
#include "caa/CaaFtaExtractor.h"
#include "caa/CaaGeometryExtractor.h"
#include "caa/CaaIdentityResolver.h"
#include "caa/CaaLinkedDocumentResolver.h"
#include "caa/CaaNativeFeatureExtractors.h"
#include "caa/CaaPartEnumerator.h"
#include "caa/CaaProductEnumerator.h"
#include "caa/CaaPropertyExtractors.h"
#include "caa/CaaRuntime.h"
#include "caa/CaaSketchExtractor.h"
#include "caa/CaaTessellationExtractor.h"
#include "caa/CaaTopologyExtractor.h"
#include "model/CaptureIdRegistry.h"
#include "output/ArtifactRepository.h"
#include "reconstruction/ReconstructionPlanner.h"
#include "reconstruction/ReconstructionValidator.h"
#include <map>

namespace cadcapture {

static void UpdateReportCounts(const ReconstructionPackage& package, CaptureReport& report)
{
  report.document_count = static_cast<int>(package.document_graph.documents.size());
  report.object_count = static_cast<int>(package.objects.size());
  report.occurrence_count = static_cast<int>(package.occurrence_graph.object_occurrences.size() +
                                             package.product_occurrences.size());
  report.property_count = static_cast<int>(package.properties.size());
  report.semantic_facet_count = static_cast<int>(package.semantic_facets.size());
  report.topology_count = static_cast<int>(package.topology.size());
  report.geometry_count = static_cast<int>(package.geometry.size());
  report.pmi_count = static_cast<int>(package.pmi.size());
}

static void SyncReportDiagnostics(const ReconstructionPackage& package, CaptureReport& report)
{
  report.diagnostics = package.diagnostics;
}

static void BuildSelfTestPackage(ReconstructionPackage& package, CaptureReport& report)
{
  DocumentEntity document;
  document.document_id = "doc_self_test";
  document.document_kind = "self_test";
  document.source_file_name = "self-test";
  document.capture_status = "complete";
  document.native_document_open_status = "not_required";
  package.document_graph.AddDocument(document);

  ObjectEntity object;
  object.object_id = "object_self_test";
  object.document_id = document.document_id;
  object.object_kind = "self_test_root";
  object.capture_status = "complete";
  package.objects.push_back(object);

  ObjectOccurrence occurrence;
  occurrence.occurrence_id = "occurrence_self_test";
  occurrence.object_id = object.object_id;
  occurrence.document_id = document.document_id;
  occurrence.occurrence_path = "/self-test";
  occurrence.capture_status = "complete";
  package.occurrence_graph.object_occurrences.push_back(occurrence);

  PropertyFact fact;
  fact.property_id = "property_self_test";
  fact.subject_id = object.object_id;
  fact.tab_id = "attributes";
  fact.tab_label = "Attributes";
  fact.group_id = "self_test";
  fact.group_label = "Self test";
  fact.group = "self_test";
  fact.key = "status";
  fact.display_name = "Status";
  fact.raw_value = "ok";
  fact.display_value = "ok";
  fact.value_type = "string";
  fact.source_api = "core";
  fact.read_status = "available";
  fact.authority = "self_test";
  fact.display_order = 1;
  fact.read_only = true;
  package.properties.push_back(fact);

  SemanticFacet facet;
  facet.facet_id = "semantic_facet_self_test";
  facet.subject_id = object.object_id;
  facet.facet_kind = "native_feature_type";
  facet.canonical_family = "self_test";
  facet.decoder_id = "self_test";
  facet.decode_level = "type_only";
  facet.decode_status = "available";
  facet.payload_extraction_status = "not_required";
  facet.source_api = "core";
  facet.read_status = "available";
  package.semantic_facets.push_back(facet);

  package.capture_status = "complete";
  package.diagnostics.push_back(MakeDiagnostic("info", "self_test_package", document.document_id,
                                               "self-test package constructed", "self_test"));
  SyncReportDiagnostics(package, report);
}

static ProductReferenceEntity* FindProductReference(ReconstructionPackage& package,
                                                    const std::string& reference_id)
{
  size_t i;
  for (i = 0; i < package.product_references.size(); ++i)
  {
    if (package.product_references[i].reference_id == reference_id)
      return &package.product_references[i];
  }
  return 0;
}

static bool ProjectLinkedCatPartDefinitions(CaaPartEnumerator& part_enumerator,
                                            CaptureIdRegistry& ids,
                                            ReconstructionPackage& package,
                                            std::string& error)
{
  std::map<std::string, PartDefinition> definitions_by_document;
  size_t i;
  for (i = 0; i < package.product_references.size(); ++i)
  {
    ProductReferenceEntity& reference = package.product_references[i];
    if (reference.reference_document_kind != "catpart" ||
        reference.referenced_document_id.empty() ||
        reference.reference_document_name.empty())
      continue;
    if (definitions_by_document.find(reference.referenced_document_id) != definitions_by_document.end())
      continue;

    CaaDocumentHandle linked_handle;
    std::string open_error;
    if (!linked_handle.OpenReadOnly(reference.reference_document_name, open_error))
    {
      reference.definition_status = "broken_reference_document";
      package.diagnostics.push_back(MakeDiagnostic("warning", "linked_catpart_open_failed",
                                                   reference.reference_id,
                                                   open_error,
                                                   "model_capture_engine"));
      continue;
    }

    PartDefinition definition;
    definition.document_id = reference.referenced_document_id;
    std::string capture_error;
    if (!part_enumerator.CaptureDefinition(linked_handle, ids, definition, package, capture_error))
    {
      reference.definition_status = "definition_capture_failed";
      package.diagnostics.push_back(MakeDiagnostic("warning", "linked_catpart_definition_failed",
                                                   reference.reference_id,
                                                   capture_error,
                                                   "model_capture_engine"));
      continue;
    }
    reference.definition_status = "definition_captured";
    definitions_by_document[reference.referenced_document_id] = definition;
  }

  for (i = 0; i < package.product_occurrences.size(); ++i)
  {
    ProductOccurrence& occurrence = package.product_occurrences[i];
    ProductReferenceEntity* reference = FindProductReference(package, occurrence.reference_id);
    if (!reference || reference->reference_document_kind != "catpart")
      continue;
    std::map<std::string, PartDefinition>::iterator found = definitions_by_document.find(reference->referenced_document_id);
    if (found == definitions_by_document.end())
      continue;

    const size_t before = package.occurrence_graph.object_occurrences.size();
    ProjectionContext context;
    context.parent_occurrence_id = occurrence.occurrence_id;
    context.tree_path_prefix = occurrence.tree_path;
    context.occurrence_path_prefix = occurrence.occurrence_path;
    context.product_occurrence_id = occurrence.occurrence_id;
    context.reference_id = occurrence.reference_id;
    context.referenced_document_id = reference->referenced_document_id;
    if (!part_enumerator.ProjectDefinition(found->second, context, ids, package, error))
      return false;
    if (package.occurrence_graph.object_occurrences.size() > before)
      occurrence.feature_definition_root_id = package.occurrence_graph.object_occurrences[before].occurrence_id;
  }
  return true;
}

bool ModelCaptureEngine::Capture(const CaptureRequest& request,
                                 const CapturePolicy& policy,
                                 ReconstructionPackage& package,
                                 CaptureReport& report,
                                 std::string& error)
{
  (void)policy;
  report.stage = "validate_request";
  if (request.self_test && request.probe_runtime)
  {
    error = "choose only one command mode";
    report.message = error;
    report.exit_code = 2;
    return false;
  }

  if (request.self_test)
  {
    BuildSelfTestPackage(package, report);
    ReconstructionPlanner planner;
    ReconstructionValidator validator;
    planner.Plan(package);
    if (!validator.Validate(package, error))
    {
      report.message = error;
      report.exit_code = 1;
      return false;
    }
    UpdateReportCounts(package, report);
    report.success = true;
    report.exit_code = 0;
    report.stage = "complete";
    report.message = "self-test passed";
    return true;
  }

  if (request.probe_runtime)
  {
    CaaRuntime runtime;
    if (!runtime.Open(error))
    {
      report.message = error;
      report.exit_code = 1;
      return false;
    }
    runtime.Close();
    report.success = true;
    report.exit_code = 0;
    report.stage = "complete";
    report.message = "runtime probe passed";
    return true;
  }

  if (request.input_path.empty() || request.output_dir.empty())
  {
    error = "input and output are required";
    report.message = error;
    report.exit_code = 2;
    return false;
  }

  CaaRuntime runtime;
  if (!runtime.Open(error))
  {
    report.message = error;
    report.exit_code = 1;
    return false;
  }

  CaaDocumentHandle document_handle;
  CaptureIdRegistry ids;
  CaaDocumentScanner scanner;
  if (!scanner.Scan(request.input_path, document_handle, ids, package, error))
  {
    report.message = error;
    report.exit_code = 2;
    UpdateReportCounts(package, report);
    SyncReportDiagnostics(package, report);
    return false;
  }

  CaaCapabilityBroker broker;
  CaaPartEnumerator part_enumerator;
  CaaProductEnumerator product_enumerator;
  CaaLinkedDocumentResolver linked_document_resolver;
  CaaPropertyExtractors property_extractors;
  CaaNativeFeatureExtractors native_feature_extractors;
  CaaSketchExtractor sketch_extractor;
  CaaTopologyExtractor topology_extractor;
  CaaGeometryExtractor geometry_extractor;
  CaaTessellationExtractor tessellation_extractor;
  CaaFtaExtractor fta_extractor;
  CaaIdentityResolver identity_resolver;
  ReconstructionPlanner planner;
  ReconstructionValidator validator;
  ArtifactRepository repository;

  broker.Check("native_access", package);
  if (!part_enumerator.Enumerate(document_handle, ids, package, error))
  {
    report.message = error;
    report.exit_code = 1;
    UpdateReportCounts(package, report);
    SyncReportDiagnostics(package, report);
    return false;
  }
  if (!product_enumerator.Enumerate(document_handle, ids, package, error))
  {
    report.message = error;
    report.exit_code = 1;
    UpdateReportCounts(package, report);
    SyncReportDiagnostics(package, report);
    return false;
  }
  if (!ProjectLinkedCatPartDefinitions(part_enumerator, ids, package, error))
  {
    report.message = error;
    report.exit_code = 1;
    UpdateReportCounts(package, report);
    SyncReportDiagnostics(package, report);
    return false;
  }
  linked_document_resolver.Resolve(document_handle, ids, package);
  property_extractors.Extract(ids, package);
  native_feature_extractors.Extract(ids, package);
  sketch_extractor.Extract(package);
  topology_extractor.Extract(document_handle, ids, package);
  geometry_extractor.Extract(package);
  tessellation_extractor.Extract(package);
  fta_extractor.Extract(document_handle, ids, package);
  identity_resolver.Resolve(ids, package);

  planner.Plan(package);
  package.capture_status = "partial";
  UpdateReportCounts(package, report);
  if (policy.validate_before_commit && !validator.Validate(package, error))
  {
    report.message = error;
    report.exit_code = 1;
    SyncReportDiagnostics(package, report);
    return false;
  }
  report.success = true;
  report.exit_code = 0;
  report.stage = "complete";
  report.message = "native tree capture completed";
  SyncReportDiagnostics(package, report);
  if (!repository.Commit(package, report, request.output_dir, request.pretty, error))
  {
    report.success = false;
    report.message = error;
    report.exit_code = 1;
    return false;
  }

  UpdateReportCounts(package, report);
  return true;
}

}
