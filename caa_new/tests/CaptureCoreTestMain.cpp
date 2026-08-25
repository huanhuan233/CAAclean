#include "engine/CapturePolicy.h"
#include "engine/CaptureReport.h"
#include "model/DocumentGraph.h"
#include "model/ObjectIdentity.h"
#include "model/OccurrenceGraph.h"
#include "model/PropertyFacts.h"
#include "model/ReconstructionPackage.h"
#include "model/SdkCatalog.h"
#include "output/JsonSupport.h"
#include "reconstruction/ReconstructionPlanner.h"
#include "reconstruction/ReconstructionValidator.h"
#include <iostream>
#include <string>

using namespace cadcapture;

static int g_failed = 0;

static void Check(bool condition, const std::string& name)
{
  if (!condition)
  {
    std::cerr << "FAIL: " << name << "\n";
    ++g_failed;
  }
}

static ReconstructionPackage MakeValidPackage()
{
  ReconstructionPackage package;
  DocumentEntity document;
  document.document_id = "doc_1";
  document.document_kind = "catpart";
  document.source_file_name = "dummy.CATPart";
  document.capture_status = "partial";
  package.document_graph.AddDocument(document);

  ObjectEntity object;
  object.object_id = "object_1";
  object.document_id = "doc_1";
  object.object_kind = "part";
  object.display_name = "PartBody";
  object.internal_name = "PartBody";
  object.startup_type = "MechanicalPart";
  object.update_status = "unknown";
  package.objects.push_back(object);

  ObjectOccurrence occurrence;
  occurrence.occurrence_id = "occurrence_1";
  occurrence.object_id = "object_1";
  occurrence.document_id = "doc_1";
  occurrence.parent_occurrence_id = "occurrence_root";
  occurrence.tree_path = "/document/PartSpecContainer/PartBody";
  occurrence.occurrence_path = occurrence.tree_path;
  occurrence.source_index = 7;
  package.occurrence_graph.object_occurrences.push_back(occurrence);
  return package;
}

int main()
{
  CapturePolicy policy;
  Check(policy.allow_partial_capture, "CapturePolicy allow_partial_capture");
  Check(policy.preserve_unknown_objects, "CapturePolicy preserve_unknown_objects");
  Check(policy.enable_legacy_projection, "CapturePolicy enable_legacy_projection");
  Check(policy.validate_before_commit, "CapturePolicy validate_before_commit");

  DocumentGraph graph;
  DocumentEntity document;
  document.document_id = "doc_a";
  graph.AddDocument(document);
  Check(graph.documents.size() == 1, "DocumentGraph AddDocument");

  ObjectEntity object;
  object.object_id = "object_a";
  ObjectOccurrence occurrence_a;
  ObjectOccurrence occurrence_b;
  occurrence_a.object_id = object.object_id;
  occurrence_b.object_id = object.object_id;
  occurrence_a.occurrence_id = "occ_a";
  occurrence_b.occurrence_id = "occ_b";
  Check(object.object_id == occurrence_a.object_id, "ObjectEntity and ObjectOccurrence linked by id");
  Check(occurrence_a.occurrence_id != occurrence_b.occurrence_id, "same ObjectEntity can have two occurrences");
  object.display_name = "Pad.1";
  object.internal_name = "Pad.1";
  object.startup_type = "PartFeature";
  object.update_status = "unknown";
  occurrence_a.parent_occurrence_id = "occ_root";
  occurrence_a.tree_path = "/document/PartSpecContainer/Pad.1";
  occurrence_a.source_index = 3;
  Check(object.display_name == "Pad.1" && object.startup_type == "PartFeature", "ObjectEntity preserves native names and startup type");
  Check(occurrence_a.parent_occurrence_id == "occ_root" && occurrence_a.tree_path.find("/document/") == 0, "ObjectOccurrence preserves parent and tree path");
  Check(occurrence_a.source_index == 3, "ObjectOccurrence preserves source index");

  PropertyFact fact;
  fact.raw_value = "25.4";
  fact.raw_unit = "mm";
  fact.display_value = "1.0";
  fact.display_unit = "in";
  Check(fact.raw_value == "25.4" && fact.display_unit == "in", "PropertyFact raw/display values and units");

  ReconstructionPackage package = MakeValidPackage();
  PropertyFact package_fact;
  package_fact.subject_id = "object_1";
  package_fact.key = "name";
  package.properties.push_back(package_fact);
  ReconstructionPlanner planner;
  planner.Plan(package);
  Check(package.reconstruction_plan == "tree_properties", "ReconstructionPlanner tree_properties");

  ReconstructionValidator validator;
  std::string error;
  Check(validator.Validate(package, error), "ReconstructionValidator accepts valid package");

  ReconstructionPackage invalid = MakeValidPackage();
  invalid.occurrence_graph.object_occurrences[0].object_id = "missing";
  planner.Plan(invalid);
  Check(!validator.Validate(invalid, error), "ReconstructionValidator rejects dangling object_id");

  Check(JsonEscape("a\"b\\c\n") == "a\\\"b\\\\c\\n", "JSON string escaping");

  CaptureReport report;
  report.AddDiagnostic("info", "i", "s", "message", "stage");
  report.AddDiagnostic("error", "e", "s", "bad", "stage");
  Check(report.diagnostics.size() == 2, "CaptureReport diagnostics");
  Check(report.HasErrors(), "CaptureReport error count");

  Check(SdkCatalog::IsStageAtLeast("runtime_verified", "compile_verified"), "Capability stage ordering");
  Check(!SdkCatalog::IsStageAtLeast("extractor_implemented", "fixture_verified"), "fixture verification gates implemented claims");

  SdkCatalog catalog;
  std::string catalog_error;
  Check(catalog.LoadCapabilityCoverage("catalog\\capability_coverage.json", catalog_error), "Capability catalog loads");
  Check(catalog.CapabilityCount() >= 3, "Capability catalog count");
  const CapabilityRecord* runtime_capability = catalog.FindCapability("caa.session.runtime");
  Check(runtime_capability != 0, "Capability lookup");
  Check(runtime_capability != 0 && runtime_capability->status == "runtime_verified", "Runtime capability status");
  Check(catalog.CapabilityAtLeast("document.extension.classification", "fixture_verified"), "fixture verified capability query");
  Check(!catalog.CapabilityAtLeast("part.bootstrap.root", "fixture_verified"), "non-fixture capability is not declared fixture verified");

  if (g_failed == 0)
  {
    std::cout << "CaptureCoreTests passed\n";
    return 0;
  }
  std::cerr << "CaptureCoreTests failed: " << g_failed << "\n";
  return 1;
}
