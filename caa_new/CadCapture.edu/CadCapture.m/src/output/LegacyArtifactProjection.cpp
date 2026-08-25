#include "output/LegacyArtifactProjection.h"
#include "output/JsonSupport.h"
#include <fstream>
#include <map>

namespace cadcapture {

std::string LegacyArtifactProjection::ProjectionStatus(const ReconstructionPackage& package) const
{
  (void)package;
  return "tree_projection_enabled";
}

static bool WriteLegacyText(const std::string& path, const std::string& text, std::string& error)
{
  std::ofstream out(path.c_str(), std::ios::out | std::ios::binary);
  if (!out)
  {
    error = "failed to open output file: " + path;
    return false;
  }
  out << text;
  return true;
}

static const ObjectEntity* FindObject(const ReconstructionPackage& package, const std::string& object_id)
{
  size_t i;
  for (i = 0; i < package.objects.size(); ++i)
  {
    if (package.objects[i].object_id == object_id)
      return &package.objects[i];
  }
  return 0;
}

static bool FinishLegacyStream(std::ofstream& out, const std::string& path, std::string& error)
{
  out.flush();
  if (!out)
  {
    error = "failed to write output file: " + path;
    return false;
  }
  out.close();
  if (!out)
  {
    error = "failed to close output file: " + path;
    return false;
  }
  return true;
}

bool LegacyArtifactProjection::Write(const ReconstructionPackage& package,
                                     const std::string& output_dir,
                                     std::string& error) const
{
  const std::string features_path = output_dir + "\\features.jsonl";
  std::ofstream features(features_path.c_str(), std::ios::out | std::ios::binary);
  if (!features)
  {
    error = "failed to open output file: " + features_path;
    return false;
  }
  size_t i;
  for (i = 0; i < package.product_occurrences.size(); ++i)
  {
    const ProductOccurrence& occurrence = package.product_occurrences[i];
    features << "{"
             << JsonQuote("feature_id") << ":" << JsonQuote(occurrence.occurrence_id) << ","
             << JsonQuote("node_kind") << ":" << JsonQuote("product_instance") << ","
             << JsonQuote("parent_id") << ":" << JsonQuote(occurrence.parent_occurrence_id) << ","
             << JsonQuote("reference_id") << ":" << JsonQuote(occurrence.reference_id) << ","
             << JsonQuote("referenced_document_id") << ":" << JsonQuote(occurrence.referenced_document_id) << ","
             << JsonQuote("instance_name") << ":" << JsonQuote(occurrence.instance_name) << ","
             << JsonQuote("part_number") << ":" << JsonQuote(occurrence.part_number) << ","
             << JsonQuote("tree_path") << ":" << JsonQuote(occurrence.tree_path) << ","
             << JsonQuote("occurrence_path") << ":" << JsonQuote(occurrence.occurrence_path) << ","
             << JsonQuote("source_index") << ":" << occurrence.source_index << ","
             << JsonQuote("transform_status") << ":" << JsonQuote(occurrence.transform_status) << ","
             << JsonQuote("load_status") << ":" << JsonQuote(occurrence.load_status) << ","
             << JsonQuote("decode_status") << ":" << JsonQuote(occurrence.capture_status)
             << "}\n";
    if (!features)
    {
      error = "failed to write output file: " + features_path;
      return false;
    }
  }
  for (i = 0; i < package.occurrence_graph.object_occurrences.size(); ++i)
  {
    const ObjectOccurrence& occurrence = package.occurrence_graph.object_occurrences[i];
    const ObjectEntity* object = FindObject(package, occurrence.object_id);
    if (!object)
    {
      error = "legacy projection missing object_id: " + occurrence.object_id;
      return false;
    }
    features << "{"
             << JsonQuote("feature_id") << ":" << JsonQuote(occurrence.occurrence_id) << ","
             << JsonQuote("node_kind") << ":" << JsonQuote(occurrence.occurrence_kind.empty() ? "native_feature" : occurrence.occurrence_kind) << ","
             << JsonQuote("source_object_id") << ":" << JsonQuote(occurrence.object_id) << ","
             << JsonQuote("parent_id") << ":" << JsonQuote(occurrence.parent_occurrence_id) << ","
             << JsonQuote("document_id") << ":" << JsonQuote(occurrence.document_id) << ","
             << JsonQuote("display_name") << ":" << JsonQuote(object->display_name) << ","
             << JsonQuote("internal_name") << ":" << JsonQuote(object->internal_name) << ","
             << JsonQuote("startup_type") << ":" << JsonQuote(object->startup_type) << ","
             << JsonQuote("tree_path") << ":" << JsonQuote(occurrence.tree_path) << ","
             << JsonQuote("occurrence_path") << ":" << JsonQuote(occurrence.occurrence_path) << ","
             << JsonQuote("source_index") << ":" << occurrence.source_index << ","
             << JsonQuote("native_enumeration_index") << ":" << occurrence.source_index << ","
             << JsonQuote("container_index") << ":" << occurrence.container_index << ","
             << JsonQuote("container_enumeration_index") << ":" << occurrence.container_index << ","
             << JsonQuote("occurrence_role") << ":" << JsonQuote(occurrence.occurrence_role) << ","
             << JsonQuote("enumeration_source") << ":" << JsonQuote(occurrence.enumeration_source) << ","
             << JsonQuote("presentation_status") << ":" << JsonQuote(occurrence.presentation_status) << ","
             << JsonQuote("update_status") << ":" << JsonQuote(object->update_status) << ","
             << JsonQuote("decode_status") << ":" << JsonQuote(occurrence.capture_status)
             << "}\n";
    if (!features)
    {
      error = "failed to write output file: " + features_path;
      return false;
    }
  }
  if (!FinishLegacyStream(features, features_path, error))
    return false;

  const std::string relations_path = output_dir + "\\relations.jsonl";
  std::ofstream relations(relations_path.c_str(), std::ios::out | std::ios::binary);
  if (!relations)
  {
    error = "failed to open output file: " + relations_path;
    return false;
  }
  for (i = 0; i < package.occurrence_graph.object_occurrences.size(); ++i)
  {
    const ObjectOccurrence& occurrence = package.occurrence_graph.object_occurrences[i];
    if (occurrence.parent_occurrence_id.empty())
      continue;
    relations << "{"
              << JsonQuote("kind") << ":" << JsonQuote("parent_of") << ","
              << JsonQuote("from_id") << ":" << JsonQuote(occurrence.parent_occurrence_id) << ","
              << JsonQuote("to_id") << ":" << JsonQuote(occurrence.occurrence_id)
              << "}\n";
    if (!relations)
    {
      error = "failed to write output file: " + relations_path;
      return false;
    }
  }
  for (i = 0; i < package.product_occurrences.size(); ++i)
  {
    const ProductOccurrence& occurrence = package.product_occurrences[i];
    if (occurrence.parent_occurrence_id.empty())
      continue;
    relations << "{"
              << JsonQuote("kind") << ":" << JsonQuote("parent_of") << ","
              << JsonQuote("from_id") << ":" << JsonQuote(occurrence.parent_occurrence_id) << ","
              << JsonQuote("to_id") << ":" << JsonQuote(occurrence.occurrence_id)
              << "}\n";
    relations << "{"
              << JsonQuote("kind") << ":" << JsonQuote("contains") << ","
              << JsonQuote("from_id") << ":" << JsonQuote(occurrence.parent_occurrence_id) << ","
              << JsonQuote("to_id") << ":" << JsonQuote(occurrence.occurrence_id)
              << "}\n";
    if (!relations)
    {
      error = "failed to write output file: " + relations_path;
      return false;
    }
  }
  if (!FinishLegacyStream(relations, relations_path, error))
    return false;

  const std::string parameters_path = output_dir + "\\parameters.jsonl";
  std::ofstream parameters(parameters_path.c_str(), std::ios::out | std::ios::binary);
  if (!parameters)
  {
    error = "failed to open output file: " + parameters_path;
    return false;
  }
  for (i = 0; i < package.properties.size(); ++i)
  {
    const PropertyFact& fact = package.properties[i];
    parameters << "{"
               << JsonQuote("parameter_id") << ":" << JsonQuote(fact.property_id) << ","
               << JsonQuote("feature_id") << ":" << JsonQuote(fact.subject_id) << ","
               << JsonQuote("name") << ":" << JsonQuote(fact.key) << ","
               << JsonQuote("display_name") << ":" << JsonQuote(fact.display_name) << ","
               << JsonQuote("raw_value") << ":" << JsonQuote(fact.raw_value) << ","
               << JsonQuote("raw_unit") << ":" << JsonQuote(fact.raw_unit) << ","
               << JsonQuote("display_value") << ":" << JsonQuote(fact.display_value) << ","
               << JsonQuote("display_unit") << ":" << JsonQuote(fact.display_unit) << ","
               << JsonQuote("value_type") << ":" << JsonQuote(fact.value_type) << ","
               << JsonQuote("source_api") << ":" << JsonQuote(fact.source_api) << ","
               << JsonQuote("read_status") << ":" << JsonQuote(fact.read_status)
               << "}\n";
    if (!parameters)
    {
      error = "failed to write output file: " + parameters_path;
      return false;
    }
  }
  if (!FinishLegacyStream(parameters, parameters_path, error))
    return false;

  const std::string native_features_path = output_dir + "\\native_features.jsonl";
  std::ofstream native_features(native_features_path.c_str(), std::ios::out | std::ios::binary);
  if (!native_features)
  {
    error = "failed to open output file: " + native_features_path;
    return false;
  }
  for (i = 0; i < package.semantic_facets.size(); ++i)
  {
    const SemanticFacet& facet = package.semantic_facets[i];
    native_features << "{"
                    << JsonQuote("native_feature_id") << ":" << JsonQuote(facet.facet_id) << ","
                    << JsonQuote("feature_id") << ":" << JsonQuote(facet.subject_id) << ","
                    << JsonQuote("facet_kind") << ":" << JsonQuote(facet.facet_kind) << ","
                    << JsonQuote("canonical_family") << ":" << JsonQuote(facet.canonical_family) << ","
                    << JsonQuote("decoder_id") << ":" << JsonQuote(facet.decoder_id) << ","
                    << JsonQuote("decode_level") << ":" << JsonQuote(facet.decode_level) << ","
                    << JsonQuote("decode_status") << ":" << JsonQuote(facet.decode_status) << ","
                    << JsonQuote("payload_extraction_status") << ":" << JsonQuote(facet.payload_extraction_status) << ","
                    << JsonQuote("source_api") << ":" << JsonQuote(facet.source_api) << ","
                    << JsonQuote("read_status") << ":" << JsonQuote(facet.read_status)
                    << "}\n";
    if (!native_features)
    {
      error = "failed to write output file: " + native_features_path;
      return false;
    }
  }
  if (!FinishLegacyStream(native_features, native_features_path, error))
    return false;

  const std::string native_topology_path = output_dir + "\\native_topology.jsonl";
  std::ofstream native_topology(native_topology_path.c_str(), std::ios::out | std::ios::binary);
  if (!native_topology)
  {
    error = "failed to open output file: " + native_topology_path;
    return false;
  }
  for (i = 0; i < package.topology.size(); ++i)
  {
    const TopologyEntity& entity = package.topology[i];
    native_topology << "{"
                    << JsonQuote("topology_id") << ":" << JsonQuote(entity.topology_id) << ","
                    << JsonQuote("source_feature_id") << ":" << JsonQuote(entity.subject_id) << ","
                    << JsonQuote("body_id") << ":" << JsonQuote(entity.topology_kind == "body" ? entity.topology_id : entity.parent_topology_id) << ","
                    << JsonQuote("topology_kind") << ":" << JsonQuote(entity.topology_kind) << ","
                    << JsonQuote("dimension") << ":" << entity.dimension << ","
                    << JsonQuote("topology_index") << ":" << entity.topology_index << ","
                    << JsonQuote("vertex_count") << ":" << entity.vertex_count << ","
                    << JsonQuote("edge_count") << ":" << entity.edge_count << ","
                    << JsonQuote("face_count") << ":" << entity.face_count << ","
                    << JsonQuote("volume_count") << ":" << entity.volume_count << ","
                    << JsonQuote("domain_count") << ":" << entity.domain_count << ","
                    << JsonQuote("internal_domain_count") << ":" << entity.internal_domain_count << ","
                    << JsonQuote("has_center") << ":" << (entity.has_center ? "true" : "false") << ","
                    << JsonQuote("center_mm") << ":[" << entity.center_mm[0] << "," << entity.center_mm[1] << "," << entity.center_mm[2] << "],"
                    << JsonQuote("area_mm2_available") << ":" << (entity.area_mm2_available ? "true" : "false") << ","
                    << JsonQuote("area_mm2") << ":" << entity.area_mm2 << ","
                    << JsonQuote("length_mm_available") << ":" << (entity.length_mm_available ? "true" : "false") << ","
                    << JsonQuote("length_mm") << ":" << entity.length_mm << ","
                    << JsonQuote("geometry_status") << ":" << JsonQuote(entity.geometry_status) << ","
                    << JsonQuote("measure_status") << ":" << JsonQuote(entity.measure_status) << ","
                    << JsonQuote("read_status") << ":" << JsonQuote(entity.read_status) << ","
                    << JsonQuote("value_source") << ":" << JsonQuote(entity.value_source)
                    << "}\n";
    if (!native_topology)
    {
      error = "failed to write output file: " + native_topology_path;
      return false;
    }
  }
  if (!FinishLegacyStream(native_topology, native_topology_path, error))
    return false;

  const std::string native_mesh_path = output_dir + "\\native_mesh_face_map.jsonl";
  std::ofstream native_mesh(native_mesh_path.c_str(), std::ios::out | std::ios::binary);
  if (!native_mesh)
  {
    error = "failed to open output file: " + native_mesh_path;
    return false;
  }
  for (i = 0; i < package.geometry.size(); ++i)
  {
    const GeometryEntity& entity = package.geometry[i];
    native_mesh << "{"
                << JsonQuote("mesh_map_id") << ":" << JsonQuote(entity.geometry_id) << ","
                << JsonQuote("body_id") << ":" << JsonQuote(entity.body_topology_id) << ","
                << JsonQuote("face_cell_id") << ":" << JsonQuote(entity.topology_id) << ","
                << JsonQuote("primitive_index") << ":" << entity.primitive_index << ","
                << JsonQuote("triangle_start") << ":" << entity.triangle_start << ","
                << JsonQuote("triangle_count") << ":" << entity.triangle_count << ","
                << JsonQuote("point_count") << ":" << entity.point_count << ","
                << JsonQuote("isolated_triangle_count") << ":" << entity.isolated_triangle_count << ","
                << JsonQuote("strip_count") << ":" << entity.strip_count << ","
                << JsonQuote("fan_count") << ":" << entity.fan_count << ","
                << JsonQuote("polygon_count") << ":" << entity.polygon_count << ","
                << JsonQuote("estimated_triangle_count") << ":" << entity.estimated_triangle_count << ","
                << JsonQuote("face_orientation_side") << ":" << entity.face_orientation_side << ","
                << JsonQuote("planar") << ":" << (entity.planar ? "true" : "false") << ","
                << JsonQuote("tessellation_status") << ":" << JsonQuote(entity.representation_status) << ","
                << JsonQuote("value_source") << ":" << JsonQuote(entity.value_source)
                << "}\n";
    if (!native_mesh)
    {
      error = "failed to write output file: " + native_mesh_path;
      return false;
    }
  }
  if (!FinishLegacyStream(native_mesh, native_mesh_path, error))
    return false;

  const std::string fta_sets_path = output_dir + "\\fta_sets.jsonl";
  std::ofstream fta_sets(fta_sets_path.c_str(), std::ios::out | std::ios::binary);
  if (!fta_sets)
  {
    error = "failed to open output file: " + fta_sets_path;
    return false;
  }
  for (i = 0; i < package.pmi.size(); ++i)
  {
    const PmiEntity& entity = package.pmi[i];
    fta_sets << "{"
             << JsonQuote("fta_set_id") << ":" << JsonQuote(entity.pmi_id) << ","
             << JsonQuote("document_id") << ":" << JsonQuote(entity.subject_id) << ","
             << JsonQuote("set_index") << ":" << entity.set_index << ","
             << JsonQuote("tps_count") << ":" << entity.tps_count << ","
             << JsonQuote("geometry_reference_count") << ":" << entity.geometry_reference_count << ","
             << JsonQuote("read_status") << ":" << JsonQuote(entity.read_status) << ","
             << JsonQuote("evidence_status") << ":" << JsonQuote(entity.evidence_status) << ","
             << JsonQuote("source_api") << ":" << JsonQuote(entity.source_api)
             << "}\n";
    if (!fta_sets)
    {
      error = "failed to write output file: " + fta_sets_path;
      return false;
    }
  }
  if (!FinishLegacyStream(fta_sets, fta_sets_path, error))
    return false;

  const std::string feature_results_path = output_dir + "\\native_feature_results.jsonl";
  std::ofstream feature_results(feature_results_path.c_str(), std::ios::out | std::ios::binary);
  if (!feature_results)
  {
    error = "failed to open output file: " + feature_results_path;
    return false;
  }
  for (i = 0; i < package.topology.size(); ++i)
  {
    const TopologyEntity& entity = package.topology[i];
    if (entity.source_kind != "catishapefeaturebody_resultout")
      continue;
    feature_results << "{"
                    << JsonQuote("result_id") << ":" << JsonQuote(entity.topology_id) << ","
                    << JsonQuote("source_feature_id") << ":" << JsonQuote(entity.subject_id) << ","
                    << JsonQuote("result_kind") << ":" << JsonQuote("resultout_body") << ","
                    << JsonQuote("vertex_count") << ":" << entity.vertex_count << ","
                    << JsonQuote("edge_count") << ":" << entity.edge_count << ","
                    << JsonQuote("face_count") << ":" << entity.face_count << ","
                    << JsonQuote("volume_count") << ":" << entity.volume_count << ","
                    << JsonQuote("read_status") << ":" << JsonQuote(entity.read_status) << ","
                    << JsonQuote("value_source") << ":" << JsonQuote(entity.value_source)
                    << "}\n";
    if (!feature_results)
    {
      error = "failed to write output file: " + feature_results_path;
      return false;
    }
  }
  if (!FinishLegacyStream(feature_results, feature_results_path, error))
    return false;

  if (!WriteLegacyText(output_dir + "\\native_feature_result_cells.jsonl", "", error))
    return false;
  if (!WriteLegacyText(output_dir + "\\native_feature_topology_links.jsonl", "", error))
    return false;
  if (!WriteLegacyText(output_dir + "\\fta_semantics.jsonl", "", error))
    return false;
  if (!WriteLegacyText(output_dir + "\\fta_topology_links.jsonl", "", error))
    return false;

  std::ostringstream capabilities;
  capabilities << "{"
               << JsonQuote("spec_tree_extraction") << ":" << JsonQuote(package.occurrence_graph.object_occurrences.empty() ? "not_available" : "partial") << ","
               << JsonQuote("native_feature_extraction") << ":" << JsonQuote(package.semantic_facets.empty() ? "not_available" : "type_only") << ","
               << JsonQuote("topology_extraction") << ":" << JsonQuote(package.topology.empty() ? "not_available" : "partial") << ","
               << JsonQuote("mesh_face_mapping") << ":" << JsonQuote(package.geometry.empty() ? "not_available" : "partial") << ","
               << JsonQuote("fta_extraction") << ":" << JsonQuote(package.pmi.empty() ? "set_scan_complete_zero_sets_or_unavailable" : "set_level_counts") << ","
               << JsonQuote("feature_result_extraction") << ":" << JsonQuote(package.feature_dependencies.empty() ? "not_available" : "resultout_body_counts") << ","
               << JsonQuote("product_instance_extraction") << ":" << JsonQuote(package.product_occurrences.empty() ? "not_available" : "complete") << ","
               << JsonQuote("native_feature_record_count") << ":" << package.semantic_facets.size() << ","
               << JsonQuote("native_topology_cell_count") << ":" << package.topology.size() << ","
               << JsonQuote("native_mesh_face_map_count") << ":" << package.geometry.size() << ","
               << JsonQuote("fta_set_count") << ":" << package.pmi.size() << ","
               << JsonQuote("product_reference_count") << ":" << package.product_references.size() << ","
               << JsonQuote("product_instance_count") << ":" << package.product_occurrences.size() << ","
               << JsonQuote("native_feature_result_count") << ":" << package.feature_dependencies.size()
               << "}\n";
  if (!WriteLegacyText(output_dir + "\\capabilities.json", capabilities.str(), error))
    return false;

  if (!ValidateRelationEndpoints(package, error))
    return false;
  return true;
}

bool LegacyArtifactProjection::ValidateRelationEndpoints(const ReconstructionPackage& package,
                                                         std::string& error) const
{
  std::map<std::string, bool> feature_ids;
  size_t i;
  for (i = 0; i < package.product_occurrences.size(); ++i)
    feature_ids[package.product_occurrences[i].occurrence_id] = true;
  for (i = 0; i < package.occurrence_graph.object_occurrences.size(); ++i)
    feature_ids[package.occurrence_graph.object_occurrences[i].occurrence_id] = true;
  for (i = 0; i < package.occurrence_graph.object_occurrences.size(); ++i)
  {
    const ObjectOccurrence& occurrence = package.occurrence_graph.object_occurrences[i];
    if (occurrence.parent_occurrence_id.empty())
      continue;
    if (feature_ids.find(occurrence.parent_occurrence_id) == feature_ids.end() ||
        feature_ids.find(occurrence.occurrence_id) == feature_ids.end())
    {
      error = "legacy_relation_endpoint_missing";
      return false;
    }
  }
  for (i = 0; i < package.product_occurrences.size(); ++i)
  {
    const ProductOccurrence& occurrence = package.product_occurrences[i];
    if (occurrence.parent_occurrence_id.empty())
      continue;
    if (feature_ids.find(occurrence.parent_occurrence_id) == feature_ids.end() ||
        feature_ids.find(occurrence.occurrence_id) == feature_ids.end())
    {
      error = "legacy_relation_endpoint_missing";
      return false;
    }
  }
  return true;
}

}
