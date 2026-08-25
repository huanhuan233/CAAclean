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
#include "output/ArtifactRepository.h"
#include "reconstruction/ReconstructionPlanner.h"
#include "reconstruction/ReconstructionValidator.h"

namespace cadcapture {

static void UpdateReportCounts(const ReconstructionPackage& package, CaptureReport& report)
{
  report.document_count = static_cast<int>(package.document_graph.documents.size());
  report.object_count = static_cast<int>(package.objects.size());
  report.occurrence_count = static_cast<int>(package.occurrence_graph.object_occurrences.size() +
                                             package.occurrence_graph.product_occurrences.size());
  report.property_count = static_cast<int>(package.properties.size());
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
  fact.subject_id = object.object_id;
  fact.group = "self_test";
  fact.key = "status";
  fact.display_name = "Status";
  fact.raw_value = "ok";
  fact.display_value = "ok";
  fact.value_type = "string";
  fact.source_api = "core";
  fact.read_status = "available";
  package.properties.push_back(fact);

  package.capture_status = "complete";
  report.AddDiagnostic("info", "self_test_package", document.document_id, "self-test package constructed", "self_test");
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

  CaaDocumentScanner scanner;
  if (!scanner.Scan(request, package, report, error))
  {
    report.message = error;
    report.exit_code = 2;
    UpdateReportCounts(package, report);
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

  broker.Check("bootstrap_native_access", package, report);
  part_enumerator.Enumerate(package, report);
  product_enumerator.Enumerate(package, report);
  linked_document_resolver.Resolve(package, report);
  property_extractors.Extract(package, report);
  native_feature_extractors.Extract(package, report);
  sketch_extractor.Extract(package, report);
  topology_extractor.Extract(package, report);
  geometry_extractor.Extract(package, report);
  tessellation_extractor.Extract(package, report);
  fta_extractor.Extract(package, report);
  identity_resolver.Resolve(package, report);

  planner.Plan(package);
  package.capture_status = "partial";
  UpdateReportCounts(package, report);
  if (policy.validate_before_commit && !validator.Validate(package, error))
  {
    report.message = error;
    report.exit_code = 1;
    return false;
  }
  report.success = true;
  report.exit_code = 0;
  report.stage = "complete";
  report.message = "bootstrap capture completed";
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
