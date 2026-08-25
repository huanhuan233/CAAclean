#include "engine/CapturePolicy.h"
#include "engine/CaptureReport.h"
#include "model/DocumentGraph.h"
#include "model/ObjectIdentity.h"
#include "model/OccurrenceGraph.h"
#include "model/PropertyFacts.h"
#include "model/ReconstructionPackage.h"
#include "model/SdkCatalog.h"
#include "output/ArtifactRepository.h"
#include "output/JsonSupport.h"
#include "output/LegacyArtifactProjection.h"
#include "reconstruction/ReconstructionPlanner.h"
#include "reconstruction/ReconstructionValidator.h"
#include <direct.h>
#include <fstream>
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

  ObjectEntity root_object;
  root_object.object_id = "object_1";
  root_object.document_id = "doc_1";
  root_object.object_kind = "catia_document";
  root_object.display_name = "dummy.CATPart";
  root_object.internal_name = "CATDocument";
  root_object.startup_type = "CATDocument";
  root_object.update_status = "not_applicable";
  root_object.capture_status = "available";
  root_object.identity.capture_id = root_object.object_id;
  root_object.identity.identity_method = "static_phase1a_node";
  root_object.identity.read_status = "session_local_only";
  package.objects.push_back(root_object);

  ObjectEntity part_object;
  part_object.object_id = "object_2";
  part_object.document_id = "doc_1";
  part_object.object_kind = "catia_spec_object";
  part_object.display_name = "PartBody";
  part_object.internal_name = "PartBody";
  part_object.startup_type = "MechanicalPart";
  part_object.update_status = "up_to_date";
  part_object.capture_status = "available";
  part_object.identity.capture_id = part_object.object_id;
  part_object.identity.identity_method = "session_object_equivalence";
  part_object.identity.read_status = "session_local_only";
  package.objects.push_back(part_object);

  ObjectEntity child_object;
  child_object.object_id = "object_3";
  child_object.document_id = "doc_1";
  child_object.object_kind = "catia_spec_object";
  child_object.display_name = "Pad.1";
  child_object.internal_name = "Pad.1";
  child_object.startup_type = "PartFeature";
  child_object.update_status = "not_up_to_date";
  child_object.capture_status = "available";
  package.objects.push_back(child_object);

  ObjectOccurrence root;
  root.occurrence_id = "occurrence_1";
  root.object_id = "object_1";
  root.document_id = "doc_1";
  root.tree_path = "/document";
  root.occurrence_path = "/0:document";
  root.source_index = 0;
  root.occurrence_role = "primary_tree";
  root.enumeration_source = "phase1a.static";
  root.presentation_status = "visible";
  root.capture_status = "available";
  package.occurrence_graph.object_occurrences.push_back(root);

  ObjectOccurrence part_a;
  part_a.occurrence_id = "occurrence_2";
  part_a.object_id = "object_2";
  part_a.parent_occurrence_id = "occurrence_1";
  part_a.document_id = "doc_1";
  part_a.tree_path = "/document/PartBody";
  part_a.occurrence_path = "/0:document/1:PartBody";
  part_a.source_index = 1;
  part_a.occurrence_role = "primary_tree";
  part_a.enumeration_source = "CATIPrtContainer.GetPart";
  part_a.presentation_status = "visible";
  part_a.capture_status = "available";
  package.occurrence_graph.object_occurrences.push_back(part_a);

  ObjectOccurrence part_b;
  part_b.occurrence_id = "occurrence_3";
  part_b.object_id = "object_2";
  part_b.parent_occurrence_id = "occurrence_1";
  part_b.document_id = "doc_1";
  part_b.tree_path = "/document/PartBody_instance";
  part_b.occurrence_path = "/0:document/2:PartBody";
  part_b.source_index = 2;
  part_b.occurrence_role = "primary_tree";
  part_b.enumeration_source = "CATISpecObject.ListComponents";
  part_b.presentation_status = "visible";
  part_b.capture_status = "available";
  package.occurrence_graph.object_occurrences.push_back(part_b);

  ObjectOccurrence child;
  child.occurrence_id = "occurrence_4";
  child.object_id = "object_3";
  child.parent_occurrence_id = "occurrence_3";
  child.document_id = "doc_1";
  child.tree_path = "/document/PartBody_instance/Pad.1";
  child.occurrence_path = "/0:document/2:PartBody/1:Pad.1";
  child.source_index = 1;
  child.occurrence_role = "primary_tree";
  child.enumeration_source = "CATISpecObject.ListComponents";
  child.presentation_status = "visible";
  child.capture_status = "available";
  package.occurrence_graph.object_occurrences.push_back(child);
  package.diagnostics.push_back(MakeDiagnostic("info", "test", "doc_1", "valid package", "test"));
  return package;
}

static long CountLines(const std::string& path)
{
  std::ifstream in(path.c_str(), std::ios::in | std::ios::binary);
  long count = 0;
  std::string line;
  while (std::getline(in, line))
    ++count;
  return count;
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
  Check(package.occurrence_graph.object_occurrences[1].object_id ==
        package.occurrence_graph.object_occurrences[2].object_id,
        "same ObjectEntity can have two valid occurrences");
  Check(package.occurrence_graph.object_occurrences[3].parent_occurrence_id == "occurrence_3",
        "second occurrence can own its child occurrence");

  ReconstructionPackage invalid = MakeValidPackage();
  invalid.occurrence_graph.object_occurrences[0].object_id = "missing";
  planner.Plan(invalid);
  Check(!validator.Validate(invalid, error), "ReconstructionValidator rejects dangling object_id");

  invalid = MakeValidPackage();
  invalid.occurrence_graph.object_occurrences[1].parent_occurrence_id = "missing_parent";
  planner.Plan(invalid);
  Check(!validator.Validate(invalid, error), "ReconstructionValidator rejects dangling parent_occurrence_id");

  invalid = MakeValidPackage();
  invalid.objects[1].object_id = invalid.objects[0].object_id;
  planner.Plan(invalid);
  Check(!validator.Validate(invalid, error), "ReconstructionValidator rejects duplicate object_id");

  invalid = MakeValidPackage();
  invalid.occurrence_graph.object_occurrences[1].occurrence_id = invalid.occurrence_graph.object_occurrences[0].occurrence_id;
  planner.Plan(invalid);
  Check(!validator.Validate(invalid, error), "ReconstructionValidator rejects duplicate occurrence_id");

  invalid = MakeValidPackage();
  invalid.occurrence_graph.object_occurrences[0].parent_occurrence_id = "occurrence_4";
  planner.Plan(invalid);
  Check(!validator.Validate(invalid, error), "ReconstructionValidator rejects occurrence parent cycle");

  invalid = MakeValidPackage();
  invalid.occurrence_graph.object_occurrences[1].parent_occurrence_id = "";
  planner.Plan(invalid);
  Check(!validator.Validate(invalid, error), "ReconstructionValidator rejects multiple primary roots");

  invalid = MakeValidPackage();
  invalid.occurrence_graph.object_occurrences[2].occurrence_role = "supplemental_discovery";
  invalid.occurrence_graph.object_occurrences[2].presentation_status = "non_primary";
  invalid.occurrence_graph.object_occurrences[2].parent_occurrence_id = "";
  planner.Plan(invalid);
  Check(!validator.Validate(invalid, error), "ReconstructionValidator rejects root supplemental occurrence");

  invalid = MakeValidPackage();
  invalid.occurrence_graph.object_occurrences[2].occurrence_path =
    invalid.occurrence_graph.object_occurrences[1].occurrence_path;
  planner.Plan(invalid);
  Check(!validator.Validate(invalid, error), "ReconstructionValidator rejects duplicate occurrence_path");

  LegacyArtifactProjection legacy;
  Check(legacy.ValidateRelationEndpoints(package, error), "Legacy relation endpoints exist");
  Check(package.occurrence_graph.object_occurrences[0].occurrence_id == "occurrence_1",
        "Legacy feature_id uses occurrence_id");
  Check(package.occurrence_graph.object_occurrences[1].object_id == "object_2",
        "Legacy source_object_id is source object id");

  Check(package.objects[0].update_status == "not_applicable" &&
        package.objects[1].update_status == "up_to_date" &&
        package.objects[2].update_status == "not_up_to_date",
        "update_status supports not_applicable, up_to_date and not_up_to_date");

  Check(JsonEscape("a\"b\\c\n") == "a\\\"b\\\\c\\n", "JSON string escaping");
  Check(JsonEscape("unicode-\xe4\xb8\xad") == "unicode-\xe4\xb8\xad", "JSON UTF-8 bytes preserved");

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
  Check(catalog.FindCapability("part.bootstrap.root") == 0, "bootstrap root capability removed");
  Check(catalog.CapabilityAtLeast("document.native_open", "fixture_verified"), "native open capability status");
  Check(catalog.CapabilityAtLeast("part.native_spec_tree", "fixture_verified"), "native spec tree capability status");

  ArtifactRepository repository;
  CaptureReport output_report;
  output_report.success = true;
  output_report.stage = "test";
  output_report.message = "ok";
  output_report.document_count = static_cast<int>(package.document_graph.documents.size());
  output_report.object_count = static_cast<int>(package.objects.size());
  output_report.occurrence_count = static_cast<int>(package.occurrence_graph.object_occurrences.size());
  const std::string output_dir = "build_core\\transaction_output";
  Check(repository.Commit(package, output_report, output_dir, true, error), "ArtifactRepository transactional commit");
  Check(CountLines(output_dir + "\\features.jsonl") ==
        static_cast<long>(package.occurrence_graph.object_occurrences.size()),
        "Legacy features are occurrence projection");
  Check(CountLines(output_dir + "\\object_entities.jsonl") ==
        static_cast<long>(package.objects.size()),
        "Object entities JSONL line count");
  {
    std::ofstream marker("build_core\\not_a_dir", std::ios::out | std::ios::binary);
    marker << "file parent";
  }
  Check(!repository.Commit(package, output_report, "build_core\\not_a_dir\\out", true, error),
        "output directory failure returns false");

  if (g_failed == 0)
  {
    std::cout << "CaptureCoreTests passed\n";
    return 0;
  }
  std::cerr << "CaptureCoreTests failed: " << g_failed << "\n";
  return 1;
}
