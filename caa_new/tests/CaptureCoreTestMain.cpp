#include "engine/CapturePolicy.h"
#include "engine/CaptureOutcome.h"
#include "model/CaptureEvidenceSummary.h"
#include "reconstruction/BrepCompleteness.h"
#include "engine/CaptureReport.h"
#include "model/DocumentGraph.h"
#include "model/ObjectIdentity.h"
#include "model/OccurrenceGraph.h"
#include "model/PropertyFacts.h"
#include "model/ReconstructionPackage.h"
#include "model/SdkCatalog.h"
#include "model/CaptureIdRegistry.h"
#include "model/GeometryStatusProjector.h"
#include "output/ArtifactRepository.h"
#include "output/JsonSupport.h"
#include "output/LegacyArtifactProjection.h"
#include "reconstruction/ReconstructionPlanner.h"
#include "reconstruction/ReconstructionValidator.h"
#include <direct.h>
#include <fstream>
#include <iostream>
#include <map>
#include <sstream>
#include <string>
#include <windows.h>

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

static ProductReferenceEntity MakeReference(const std::string& reference_id,
                                            const std::string& document_id,
                                            const std::string& part_number)
{
  ProductReferenceEntity reference;
  reference.reference_id = reference_id;
  reference.referenced_document_id = document_id;
  reference.part_number = part_number;
  reference.display_name = part_number;
  reference.reference_document_kind = "catpart";
  reference.definition_status = "captured";
  reference.value_source = "test";
  reference.identity_method = "session_reference_identity";
  return reference;
}

static ProductOccurrence MakeProductOccurrence(const std::string& occurrence_id,
                                               const std::string& parent_id,
                                               const std::string& reference_id,
                                               const std::string& document_id,
                                               const std::string& instance_name,
                                               long depth,
                                               long source_index)
{
  ProductOccurrence occurrence;
  occurrence.occurrence_id = occurrence_id;
  occurrence.parent_occurrence_id = parent_id;
  occurrence.reference_id = reference_id;
  occurrence.referenced_document_id = document_id;
  occurrence.instance_name = instance_name;
  occurrence.part_number = "PartA";
  occurrence.tree_path = parent_id.empty() ? ("/" + instance_name) : ("/Root/" + instance_name);
  occurrence.occurrence_path = parent_id.empty() ? ("/0:" + instance_name) : ("/0:Root/" + instance_name);
  occurrence.depth = depth;
  occurrence.source_index = source_index;
  occurrence.child_count = 0;
  occurrence.transform_status = depth == 0 ? "identity_root" : "resolved_absolute";
  occurrence.transform_source = depth == 0 ? "CATProduct.root" : "CATIMovable.GetAbsPosition";
  occurrence.load_status = "loaded";
  occurrence.capture_status = "available";
  occurrence.presentation_status = "visible";
  return occurrence;
}

static ReconstructionPackage MakeProductPackage()
{
  ReconstructionPackage package;
  DocumentEntity product_document;
  product_document.document_id = "doc_product";
  product_document.document_kind = "catproduct";
  product_document.source_file_name = "Root.CATProduct";
  product_document.load_status = "loaded";
  product_document.capture_status = "partial";
  package.document_graph.AddDocument(product_document);

  DocumentEntity part_document;
  part_document.document_id = "doc_part_a";
  part_document.document_kind = "catpart";
  part_document.source_file_name = "PartA.CATPart";
  part_document.load_status = "loaded";
  part_document.capture_status = "partial";
  part_document.definition_status = "captured_once";
  package.document_graph.AddDocument(part_document);

  package.product_references.push_back(MakeReference("ref_root", "doc_product", "Root"));
  package.product_references.push_back(MakeReference("ref_part_a", "doc_part_a", "PartA"));

  package.product_occurrences.push_back(MakeProductOccurrence("product_occurrence_1", "", "ref_root", "doc_product", "Root", 0, 0));
  package.product_occurrences.push_back(MakeProductOccurrence("product_occurrence_2", "product_occurrence_1", "ref_part_a", "doc_part_a", "PartA.1", 1, 1));
  package.product_occurrences.push_back(MakeProductOccurrence("product_occurrence_3", "product_occurrence_1", "ref_part_a", "doc_part_a", "PartA.2", 1, 2));

  ObjectEntity feature;
  feature.object_id = "object_part_feature_1";
  feature.document_id = "doc_part_a";
  feature.object_kind = "catia_spec_object";
  feature.display_name = "PartBody";
  feature.internal_name = "MechanicalTool.1";
  feature.startup_type = "MechanicalTool";
  feature.update_status = "up_to_date";
  feature.capture_status = "available";
  package.objects.push_back(feature);

  ObjectOccurrence feature_a;
  feature_a.occurrence_id = "occurrence_feature_1";
  feature_a.object_id = feature.object_id;
  feature_a.parent_occurrence_id = "product_occurrence_2";
  feature_a.document_id = "doc_part_a";
  feature_a.tree_path = "/Root/PartA.1/PartBody";
  feature_a.occurrence_path = "/0:Root/1:PartA.1/1:PartBody";
  feature_a.source_index = 1;
  feature_a.occurrence_role = "primary_tree";
  feature_a.enumeration_source = "definition_projection";
  feature_a.presentation_status = "visible";
  feature_a.occurrence_kind = "native_feature";
  feature_a.product_occurrence_id = "product_occurrence_2";
  feature_a.reference_id = "ref_part_a";
  feature_a.referenced_document_id = "doc_part_a";
  feature_a.capture_status = "available";
  package.occurrence_graph.object_occurrences.push_back(feature_a);

  ObjectOccurrence feature_b = feature_a;
  feature_b.occurrence_id = "occurrence_feature_2";
  feature_b.parent_occurrence_id = "product_occurrence_3";
  feature_b.tree_path = "/Root/PartA.2/PartBody";
  feature_b.occurrence_path = "/0:Root/2:PartA.2/1:PartBody";
  feature_b.product_occurrence_id = "product_occurrence_3";
  package.occurrence_graph.object_occurrences.push_back(feature_b);

  package.diagnostics.push_back(MakeDiagnostic("info", "test_product", "doc_product", "valid product package", "test"));
  return package;
}

int main()
{
  CapturePolicy policy;
  Check(policy.allow_partial_capture, "CapturePolicy allow_partial_capture");
  Check(policy.validate_before_commit, "CapturePolicy validate_before_commit");
  // 中文：可选能力未编译不应把已完成的树采集误判为部分失败；关联件失败则必须可见。
  ReconstructionPackage outcome_package;
  DocumentEntity outcome_document;
  outcome_document.document_id = "outcome_doc";
  outcome_package.document_graph.AddDocument(outcome_document);
  outcome_package.objects.push_back(ObjectEntity());
  outcome_package.occurrence_graph.object_occurrences.push_back(ObjectOccurrence());
  outcome_package.diagnostics.push_back(MakeDiagnostic("warning", "capability_unsupported", "optional",
                                                        "optional capability unavailable", "capability_broker"));
  std::string outcome_error;
  Check(CaptureOutcome::Finalize(outcome_package, policy, outcome_error),
        "optional unsupported capability does not block capture");
  Check(outcome_package.capture_status == "complete", "successful capture is complete");
  outcome_package.diagnostics.push_back(MakeDiagnostic("warning", "linked_catpart_open_failed", "part",
                                                        "linked CATPart failed", "model_capture_engine"));
  Check(CaptureOutcome::Finalize(outcome_package, policy, outcome_error),
        "default policy permits partial capture");
  Check(outcome_package.capture_status == "partial", "required stage failure is partial");
  CapturePolicy strict_policy;
  strict_policy.allow_partial_capture = false;
  Check(!CaptureOutcome::Finalize(outcome_package, strict_policy, outcome_error),
        "strict policy blocks partial capture");
  Check(outcome_error.find("linked_catpart_open_failed") != std::string::npos,
        "strict failure retains diagnostic code");
  // 中文：几何记录不等于真实三角形，关联文档状态要由真实链接和定义状态决定。
  ReconstructionPackage evidence_package;
  GeometryEntity empty_mesh;
  empty_mesh.geometry_id = "mesh_range_empty";
  empty_mesh.representation_status = "success";
  evidence_package.geometry.push_back(empty_mesh);
  Check(!CaptureEvidenceSummary::HasMesh(evidence_package), "empty mesh range is not usable mesh");
  MeshTriangleEntity actual_triangle;
  actual_triangle.triangle_id = "triangle_1";
  evidence_package.mesh_triangles.push_back(actual_triangle);
  Check(CaptureEvidenceSummary::HasMesh(evidence_package), "actual triangle is usable mesh");
  Check(CaptureEvidenceSummary::LinkedDocuments(evidence_package) == "not_applicable",
        "CATPart without links does not claim linked resolution");
  ProductReferenceEntity unresolved_reference;
  unresolved_reference.reference_id = "reference_1";
  unresolved_reference.reference_document_kind = "catpart";
  unresolved_reference.definition_status = "broken_reference_document";
  evidence_package.product_references.push_back(unresolved_reference);
  Check(CaptureEvidenceSummary::LinkedDocuments(evidence_package) == "partial",
        "broken linked CATPart is partial");
  evidence_package.product_references[0].definition_status = "definition_captured";
  evidence_package.product_references[0].referenced_document_id = "linked_doc";
  DocumentLink loaded_link;
  loaded_link.reference_id = "reference_1";
  loaded_link.link_status = "loaded";
  evidence_package.document_graph.links.push_back(loaded_link);
  Check(CaptureEvidenceSummary::LinkedDocuments(evidence_package) == "available",
        "captured linked CATPart and document link are available");

  DocumentGraph graph;
  DocumentEntity document;
  document.document_id = "doc_a";
  graph.AddDocument(document);
  Check(graph.documents.size() == 1, "DocumentGraph AddDocument");

  CaptureIdRegistry ids;
  Check(ids.NextDocumentId() != ids.NextDocumentId(), "CaptureIdRegistry document ids are unique");
  Check(ids.NextProductReferenceId().find("product_reference_") == 0, "CaptureIdRegistry product reference ids");

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
  fact.property_id = "property_test_value";
  fact.subject_id = "object_a";
  fact.tab_id = "mechanical";
  fact.group_id = "dimension";
  fact.key = "length";
  fact.raw_value = "25.4";
  fact.raw_unit = "mm";
  fact.display_value = "1.0";
  fact.display_unit = "in";
  Check(fact.raw_value == "25.4" && fact.display_unit == "in", "PropertyFact raw/display values and units");

  ReconstructionPackage package = MakeValidPackage();
  PropertyFact package_fact;
  package_fact.property_id = "property_fixture_name";
  package_fact.subject_id = "object_1";
  package_fact.tab_id = "attributes";
  package_fact.group_id = "identity";
  package_fact.key = "name";
  package.properties.push_back(package_fact);
  ReconstructionPlanner planner;
  planner.Plan(package);
  Check(package.reconstruction_plan == "tree_properties", "ReconstructionPlanner tree_properties");

  ReconstructionPackage geometry_only_package;
  GeometryEntity mesh_range;
  mesh_range.geometry_id = "geometry_range_only";
  mesh_range.geometry_kind = "tessellation";
  mesh_range.kind = GeometryTessellation;
  mesh_range.triangle_start = 0;
  mesh_range.triangle_count = 12;
  mesh_range.representation_status = "range_only";
  geometry_only_package.geometry.push_back(mesh_range);
  planner.Plan(geometry_only_package);
  Check(geometry_only_package.reconstruction_plan == "opaque_preservation",
        "ReconstructionPlanner does not treat mesh ranges as exact_brep");

  ReconstructionPackage tessellation_package;
  mesh_range.representation_status = "triangles_available";
  tessellation_package.geometry.push_back(mesh_range);
  MeshTriangleEntity tessellation_triangle;
  tessellation_triangle.triangle_id = "triangle_coordinates_1";
  tessellation_package.mesh_triangles.push_back(tessellation_triangle);
  planner.Plan(tessellation_package);
  Check(tessellation_package.reconstruction_plan == "tessellation",
        "ReconstructionPlanner selects tessellation only when triangle coordinates are available");

  ReconstructionPackage exact_package;
  TopologyEntity body;
  body.topology_id = "body_1";
  body.topology_kind = "body";
  body.read_status = "success";
  body.face_count = 1;
  body.edge_count = 1;
  body.vertex_count = 1;
  body.volume_count = 1;
  exact_package.topology.push_back(body);
  TopologyEntity face;
  face.topology_id = "face_1";
  face.topology_kind = "face";
  face.read_status = "success";
  face.parent_topology_id = "body_1";
  face.geometry_status = "exact";
  face.exact_geometry_type = "plane";
  face.geometry_parameters_json = "{\"normal\":[0,0,1]}";
  face.boundary_cell_ids.push_back("edge_1");
  exact_package.topology.push_back(face);
  TopologyEntity edge;
  edge.topology_id = "edge_1";
  edge.topology_kind = "edge";
  edge.read_status = "success";
  edge.parent_topology_id = "body_1";
  edge.geometry_status = "exact";
  edge.exact_geometry_type = "line";
  edge.geometry_parameters_json = "{\"origin\":[0,0,0]}";
  edge.boundary_cell_ids.push_back("vertex_1");
  exact_package.topology.push_back(edge);
  TopologyEntity vertex;
  vertex.topology_id = "vertex_1";
  vertex.topology_kind = "vertex";
  vertex.read_status = "success";
  vertex.parent_topology_id = "body_1";
  exact_package.topology.push_back(vertex);
  TopologyEntity volume;
  volume.topology_id = "volume_1";
  volume.topology_kind = "volume";
  volume.read_status = "success";
  volume.parent_topology_id = "body_1";
  exact_package.topology.push_back(volume);
  TopologyEntity wire_cell;
  wire_cell.topology_id = "wire_cell_1";
  wire_cell.topology_kind = "wire";
  wire_cell.parent_topology_id = "body_1";
  exact_package.topology.push_back(wire_cell);
  NativeTopologyWireEntity exact_wire;
  exact_wire.wire_id = "wire_1";
  exact_wire.body_id = "body_1";
  exact_wire.owning_face_id = "face_1";
  exact_wire.edge_count = 1;
  exact_wire.closed_status = "closed_by_edge_vertex_continuity";
  exact_package.topology_wires.push_back(exact_wire);
  NativeTopologyCoedgeEntity exact_coedge;
  exact_coedge.coedge_id = "coedge_1";
  exact_coedge.body_id = "body_1";
  exact_coedge.wire_id = "wire_1";
  exact_coedge.owning_face_id = "face_1";
  exact_coedge.edge_cell_id = "edge_1";
  exact_coedge.previous_coedge_id = "coedge_1";
  exact_coedge.next_coedge_id = "coedge_1";
  exact_package.topology_coedges.push_back(exact_coedge);
  TopologyRelation boundary;
  boundary.from_topology_id = "face_1";
  boundary.to_topology_id = "edge_1";
  boundary.relation_kind = "boundary";
  boundary.read_status = "available";
  exact_package.topology_relations.push_back(boundary);
  planner.Plan(exact_package);
  Check(exact_package.reconstruction_plan == "exact_brep",
        "ReconstructionPlanner exact_brep requires complete topology evidence");
  exact_package.topology[2].geometry_parameters_json.clear();
  planner.Plan(exact_package);
  Check(exact_package.reconstruction_plan != "exact_brep",
        "one edge without exact parameters downgrades the body");
  exact_package.topology[2].geometry_parameters_json = "{\"origin\":[0,0,0]}";
  TopologyEntity second_body = body;
  second_body.topology_id = "body_2";
  second_body.topology_kind = "feature_result_body";
  second_body.source_kind = "catishapefeaturebody_resultout";
  exact_package.topology.push_back(second_body);
  planner.Plan(exact_package);
  Check(exact_package.reconstruction_plan != "exact_brep",
        "an incomplete sibling ResultOUT body downgrades the package");
  BrepCompleteness mixed_brep = BrepCompletenessEvaluator().Evaluate(exact_package);
  Check(mixed_brep.exact_body_count == 1 && mixed_brep.incomplete_body_count == 1,
        "mixed body evidence is counted per body");
  exact_package.topology.pop_back();
  exact_package.topology_wires[0].closed_status = "open";
  Check(BrepCompletenessEvaluator().Evaluate(exact_package).exact_body_count == 0,
        "open wire prevents exact body reconstruction");
  exact_package.topology_wires[0].closed_status = "closed_by_edge_vertex_continuity";
  exact_package.topology_coedges[0].next_coedge_id = "missing_coedge";
  Check(BrepCompletenessEvaluator().Evaluate(exact_package).exact_body_count == 0,
        "dangling coedge prevents exact body reconstruction");

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

  ReconstructionPackage product_package = MakeProductPackage();
  planner.Plan(product_package);
  Check(validator.Validate(product_package, error), "ReconstructionValidator accepts valid product package");
  Check(product_package.product_references.size() == 2, "ProductReference stores definition once");
  Check(product_package.product_occurrences.size() == 3, "ProductOccurrence keeps multiple instances");
  Check(product_package.product_occurrences[1].reference_id == product_package.product_occurrences[2].reference_id,
        "two instances share one reference");
  Check(product_package.occurrence_graph.object_occurrences[0].object_id ==
        product_package.occurrence_graph.object_occurrences[1].object_id,
        "two projected feature occurrences reuse one ObjectEntity");
  Check(product_package.occurrence_graph.object_occurrences[0].occurrence_id !=
        product_package.occurrence_graph.object_occurrences[1].occurrence_id,
        "two projected feature occurrences have unique occurrence ids");
  Check(legacy.ValidateRelationEndpoints(product_package, error), "Legacy product relation endpoints exist");

  invalid = MakeProductPackage();
  invalid.product_occurrences[1].reference_id = "missing_reference";
  planner.Plan(invalid);
  Check(!validator.Validate(invalid, error), "ReconstructionValidator rejects dangling product reference");

  invalid = MakeProductPackage();
  invalid.product_occurrences[1].referenced_document_id = "missing_doc";
  planner.Plan(invalid);
  Check(!validator.Validate(invalid, error), "ReconstructionValidator rejects dangling referenced_document_id");

  invalid = MakeProductPackage();
  invalid.product_occurrences[2].occurrence_path = invalid.product_occurrences[1].occurrence_path;
  planner.Plan(invalid);
  Check(!validator.Validate(invalid, error), "ReconstructionValidator rejects duplicate product occurrence_path");

  invalid = MakeProductPackage();
  invalid.product_occurrences[1].transform_4x4.pop_back();
  planner.Plan(invalid);
  Check(!validator.Validate(invalid, error), "ReconstructionValidator rejects malformed transform matrix");

  ArtifactRepository repository;
  CaptureReport output_report;
  output_report.success = true;
  output_report.stage = "test";
  output_report.message = "ok";
  output_report.document_count = static_cast<int>(package.document_graph.documents.size());
  output_report.object_count = static_cast<int>(package.objects.size());
  output_report.occurrence_count = static_cast<int>(package.occurrence_graph.object_occurrences.size());
  const std::string output_dir = "build_core\\transaction_output";
  FtaSemanticEntity text_annotation;
  text_annotation.fta_semantic_id = "pmi_1_TPS000001";
  text_annotation.fta_set_id = "pmi_1";
  text_annotation.annotation_text = "Material = S1454_G803\nThickness = 0.33mm";
  text_annotation.annotation_text_status = "available";
  text_annotation.annotation_text_source = "CATITPSText.GetText";
  package.fta_semantics.push_back(text_annotation);
  // 中文：输出事务失败时保留原始错误，便于区分既有基线问题与本次安全检查。
  const bool committed = repository.Commit(package, output_report, output_dir, true, error);
  if (!committed)
    std::cerr << "transaction error: " << error << "\n";
  Check(committed, "ArtifactRepository transactional commit");
  {
    std::ifstream annotations((output_dir + "\\fta_semantics.jsonl").c_str());
    std::string line;
    std::getline(annotations, line);
    Check(line.find("Material = S1454_G803\\nThickness = 0.33mm") != std::string::npos,
          "FTA output preserves actual multiline text separately from validation text");
    Check(line.find("CATITPSText.GetText") != std::string::npos,
          "FTA text retains its source interface");
  }
  Check(CountLines(output_dir + "\\features.jsonl") ==
        static_cast<long>(package.occurrence_graph.object_occurrences.size()),
        "Legacy features are occurrence projection");
  Check(CountLines(output_dir + "\\object_entities.jsonl") ==
        static_cast<long>(package.objects.size()),
        "Object entities JSONL line count");
  output_report.document_count = static_cast<int>(product_package.document_graph.documents.size());
  output_report.object_count = static_cast<int>(product_package.objects.size());
  output_report.occurrence_count = static_cast<int>(product_package.occurrence_graph.object_occurrences.size() +
                                                    product_package.product_occurrences.size());
  const std::string product_output_dir = "build_core\\product_transaction_output";
  Check(repository.Commit(product_package, output_report, product_output_dir, true, error),
        "ArtifactRepository commits product package");
  Check(CountLines(product_output_dir + "\\product_references.jsonl") ==
        static_cast<long>(product_package.product_references.size()),
        "Product references JSONL line count");
  Check(CountLines(product_output_dir + "\\product_occurrences.jsonl") ==
        static_cast<long>(product_package.product_occurrences.size()),
        "Product occurrences JSONL line count");
  Check(CountLines(product_output_dir + "\\features.jsonl") ==
        static_cast<long>(product_package.occurrence_graph.object_occurrences.size() +
                          product_package.product_occurrences.size()),
        "Legacy product features include product and feature nodes");
  // 中文：安全回归仅在测试生成目录建立哨兵，验证未知业务文件绝不会被事务替换。
  const std::string foreign_output = "build_core\\foreign_output_test_v2";
  _mkdir(foreign_output.c_str());
  {
    std::ofstream sentinel((foreign_output + "\\sentinel.txt").c_str(), std::ios::out | std::ios::binary);
    sentinel << "must survive";
  }
  error.clear();
  Check(!repository.Commit(package, output_report, foreign_output, true, error),
        "unknown nonempty output is rejected");
  {
    std::ifstream sentinel((foreign_output + "\\sentinel.txt").c_str(), std::ios::in | std::ios::binary);
    Check(!!sentinel, "unknown output sentinel survives");
  }
  // 中文：历史固定名字的暂存目录不属于本次运行，提交时不可顺手清理。
  const std::string legacy_stage = "build_core\\stage_collision_test.cadcapture_stage";
  const std::string legacy_backup = "build_core\\stage_collision_test.cadcapture_backup";
  _mkdir(legacy_stage.c_str());
  _mkdir(legacy_backup.c_str());
  {
    std::ofstream sentinel((legacy_stage + "\\sentinel.txt").c_str(), std::ios::out | std::ios::binary);
    sentinel << "must survive";
  }
  {
    std::ofstream sentinel((legacy_backup + "\\sentinel.txt").c_str(), std::ios::out | std::ios::binary);
    sentinel << "must survive";
  }
  error.clear();
  Check(repository.Commit(product_package, output_report, "build_core\\stage_collision_test", true, error),
        "transaction ignores unrelated legacy stage");
  {
    std::ifstream sentinel((legacy_stage + "\\sentinel.txt").c_str(), std::ios::in | std::ios::binary);
    Check(!!sentinel, "legacy stage sentinel survives");
  }
  {
    std::ifstream sentinel((legacy_backup + "\\sentinel.txt").c_str(), std::ios::in | std::ios::binary);
    Check(!!sentinel, "legacy backup sentinel survives");
  }
  // 中文：后端会预建空目录；原生提交必须继续接受该调用方式。
  const std::string empty_output = "build_core\\precreated_empty_output_test";
  _mkdir(empty_output.c_str());
  error.clear();
  Check(repository.Commit(product_package, output_report, empty_output, true, error),
        "precreated empty output commits");
  Check(GetFileAttributesA((empty_output + "\\.cadcapture_stage_owner").c_str()) == INVALID_FILE_ATTRIBUTES,
        "committed output excludes transaction marker");
  // 中文：模拟旧输出已移到备份但新暂存无法落位，旧文件必须自动恢复。
  const std::string rollback_output = "build_core\\rollback_output_test";
  error.clear();
  Check(repository.Commit(product_package, output_report, rollback_output, true, error),
        "rollback fixture commits previous output");
  SetEnvironmentVariableA("CADCAPTURE_TEST_FAIL_AFTER_BACKUP", "1");
  error.clear();
  const bool injected_commit = repository.Commit(package, output_report, rollback_output, true, error);
  SetEnvironmentVariableA("CADCAPTURE_TEST_FAIL_AFTER_BACKUP", NULL);
  Check(!injected_commit, "injected commit failure is reported");
  Check(CountLines(rollback_output + "\\product_references.jsonl") ==
        static_cast<long>(product_package.product_references.size()),
        "previous output restored after commit failure");
  // 中文：状态必须来自同一对象的最终拓扑；文档根可继承自身最终体，兄弟对象不可串用。
  ReconstructionPackage geometry_package;
  DocumentEntity geometry_document;
  geometry_document.document_id = "geometry_doc_1";
  geometry_document.document_kind = "catpart";
  geometry_package.document_graph.AddDocument(geometry_document);
  ObjectEntity geometry_root;
  geometry_root.object_id = "geometry_root";
  geometry_root.document_id = "geometry_doc_1";
  geometry_root.object_kind = "catia_document";
  geometry_package.objects.push_back(geometry_root);
  ObjectEntity geometry_part;
  geometry_part.object_id = "geometry_part";
  geometry_part.document_id = "geometry_doc_1";
  geometry_part.startup_type = "MechanicalPart";
  geometry_package.objects.push_back(geometry_part);
  ObjectEntity geometry_pad;
  geometry_pad.object_id = "geometry_pad";
  geometry_pad.document_id = "geometry_doc_1";
  geometry_pad.startup_type = "Pad";
  geometry_package.objects.push_back(geometry_pad);
  ObjectEntity geometry_empty;
  geometry_empty.object_id = "geometry_empty";
  geometry_empty.document_id = "geometry_doc_1";
  geometry_package.objects.push_back(geometry_empty);
  TopologyEntity exact_face;
  exact_face.topology_id = "exact_face";
  exact_face.subject_id = "geometry_doc_1";
  exact_face.topology_kind = "face";
  exact_face.geometry_status = "exact";
  geometry_package.topology.push_back(exact_face);
  TopologyEntity pad_result;
  pad_result.topology_id = "pad_result";
  pad_result.subject_id = "geometry_pad";
  pad_result.topology_kind = "feature_result_body";
  geometry_package.topology.push_back(pad_result);
  GeometryStatusProjector().Apply(ids, geometry_package);
  std::map<std::string, std::string> geometry_statuses;
  for (size_t status_index = 0; status_index < geometry_package.properties.size(); ++status_index)
  {
    const PropertyFact& status = geometry_package.properties[status_index];
    if (status.key == "geometry_status")
      geometry_statuses[status.subject_id] = status.raw_value;
  }
  Check(geometry_statuses["geometry_root"] == "exact", "document root receives its exact geometry");
  Check(geometry_statuses["geometry_part"] == "exact", "MechanicalPart receives document geometry");
  Check(geometry_statuses["geometry_pad"] == "topology_only", "feature result body is not overstated as exact");
  Check(geometry_statuses["geometry_empty"] == "not_available", "sibling without evidence has no geometry");
  const size_t first_geometry_fact_count = geometry_package.properties.size();
  GeometryStatusProjector().Apply(ids, geometry_package);
  Check(geometry_package.properties.size() == first_geometry_fact_count,
        "geometry status projection is idempotent");
  TopologyEntity failed_face;
  failed_face.topology_id = "failed_face";
  failed_face.subject_id = "geometry_pad";
  failed_face.topology_kind = "face";
  failed_face.geometry_status = "failed";
  geometry_package.topology.push_back(failed_face);
  GeometryStatusProjector().Apply(ids, geometry_package);
  for (size_t failed_index = 0; failed_index < geometry_package.properties.size(); ++failed_index)
  {
    const PropertyFact& status = geometry_package.properties[failed_index];
    if (status.key == "geometry_status" && status.subject_id == "geometry_pad")
      Check(status.raw_value == "partial", "mixed topology failure remains partial");
  }
  // 中文：即使有合法 manifest，目录内混入未知文件也不能整目录替换。
  std::ostringstream mixed_name;
  mixed_name << "build_core\\mixed_output_test_" << GetCurrentProcessId() << "_" << GetTickCount();
  const std::string mixed_output = mixed_name.str();
  error.clear();
  Check(repository.Commit(product_package, output_report, mixed_output, true, error),
        "owned output fixture commits");
  {
    std::ofstream sentinel((mixed_output + "\\user-note.txt").c_str(), std::ios::out | std::ios::binary);
    sentinel << "must survive";
  }
  error.clear();
  Check(!repository.Commit(product_package, output_report, mixed_output, true, error),
        "owned output with unknown file is rejected");
  {
    std::ifstream sentinel((mixed_output + "\\user-note.txt").c_str(), std::ios::in | std::ios::binary);
    Check(!!sentinel, "mixed output sentinel survives");
  }
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
