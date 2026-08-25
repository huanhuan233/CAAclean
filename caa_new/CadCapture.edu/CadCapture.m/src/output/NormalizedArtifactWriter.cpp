#include "output/NormalizedArtifactWriter.h"
#include "output/JsonSupport.h"
#include <direct.h>
#include <errno.h>
#include <fstream>
#include <sstream>
#include <sys/stat.h>

namespace cadcapture {

static bool DirectoryExists(const std::string& path)
{
  struct _stat info;
  return _stat(path.c_str(), &info) == 0 && (info.st_mode & _S_IFDIR);
}

static bool EnsureDirectory(const std::string& path, std::string& error)
{
  if (path.empty())
  {
    error = "output directory is empty";
    return false;
  }
  if (_mkdir(path.c_str()) == 0)
    return true;
  if (errno == EEXIST && DirectoryExists(path))
    return true;
  error = "failed to create output directory: " + path;
  return false;
}

static std::string Indent(bool pretty, int depth)
{
  if (!pretty)
    return "";
  return std::string(depth * 2, ' ');
}

static std::string NewLine(bool pretty)
{
  return pretty ? "\n" : "";
}

static bool WriteText(const std::string& path, const std::string& text, std::string& error)
{
  std::ofstream out(path.c_str(), std::ios::out | std::ios::binary);
  if (!out)
  {
    error = "failed to open output file: " + path;
    return false;
  }
  out << text;
  if (!out)
  {
    error = "failed to write output file: " + path;
    return false;
  }
  return true;
}

static bool FinishStream(std::ofstream& out, const std::string& path, std::string& error)
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

static bool WriteJsonLines(const ReconstructionPackage& package,
                           const std::string& output_dir,
                           std::string& error)
{
  size_t i;
  const std::string references_path = output_dir + "\\product_references.jsonl";
  std::ofstream references(references_path.c_str(), std::ios::out | std::ios::binary);
  if (!references)
  {
    error = "failed to open output file: " + references_path;
    return false;
  }
  for (i = 0; i < package.product_references.size(); ++i)
  {
    const ProductReferenceEntity& reference = package.product_references[i];
    references << "{"
               << JsonQuote("reference_id") << ":" << JsonQuote(reference.reference_id) << ","
               << JsonQuote("referenced_document_id") << ":" << JsonQuote(reference.referenced_document_id) << ","
               << JsonQuote("part_number") << ":" << JsonQuote(reference.part_number) << ","
               << JsonQuote("display_name") << ":" << JsonQuote(reference.display_name) << ","
               << JsonQuote("reference_document_name") << ":" << JsonQuote(reference.reference_document_name) << ","
               << JsonQuote("reference_document_kind") << ":" << JsonQuote(reference.reference_document_kind) << ","
               << JsonQuote("definition_status") << ":" << JsonQuote(reference.definition_status) << ","
               << JsonQuote("identity_method") << ":" << JsonQuote(reference.identity_method) << ","
               << JsonQuote("value_source") << ":" << JsonQuote(reference.value_source)
               << "}\n";
    if (!references)
    {
      error = "failed to write output file: " + references_path;
      return false;
    }
  }
  if (!FinishStream(references, references_path, error))
    return false;

  const std::string product_occurrences_path = output_dir + "\\product_occurrences.jsonl";
  std::ofstream product_occurrences(product_occurrences_path.c_str(), std::ios::out | std::ios::binary);
  if (!product_occurrences)
  {
    error = "failed to open output file: " + product_occurrences_path;
    return false;
  }
  for (i = 0; i < package.product_occurrences.size(); ++i)
  {
    const ProductOccurrence& occurrence = package.product_occurrences[i];
    product_occurrences << "{"
                        << JsonQuote("occurrence_id") << ":" << JsonQuote(occurrence.occurrence_id) << ","
                        << JsonQuote("parent_occurrence_id") << ":" << JsonQuote(occurrence.parent_occurrence_id) << ","
                        << JsonQuote("reference_id") << ":" << JsonQuote(occurrence.reference_id) << ","
                        << JsonQuote("referenced_document_id") << ":" << JsonQuote(occurrence.referenced_document_id) << ","
                        << JsonQuote("instance_name") << ":" << JsonQuote(occurrence.instance_name) << ","
                        << JsonQuote("part_number") << ":" << JsonQuote(occurrence.part_number) << ","
                        << JsonQuote("tree_path") << ":" << JsonQuote(occurrence.tree_path) << ","
                        << JsonQuote("occurrence_path") << ":" << JsonQuote(occurrence.occurrence_path) << ","
                        << JsonQuote("depth") << ":" << occurrence.depth << ","
                        << JsonQuote("source_index") << ":" << occurrence.source_index << ","
                        << JsonQuote("child_count") << ":" << occurrence.child_count << ","
                        << JsonQuote("transform_4x4") << ":[";
    size_t j;
    for (j = 0; j < occurrence.transform_4x4.size(); ++j)
    {
      if (j != 0)
        product_occurrences << ",";
      product_occurrences << occurrence.transform_4x4[j];
    }
    product_occurrences << "],"
                        << JsonQuote("transform_status") << ":" << JsonQuote(occurrence.transform_status) << ","
                        << JsonQuote("transform_source") << ":" << JsonQuote(occurrence.transform_source) << ","
                        << JsonQuote("load_status") << ":" << JsonQuote(occurrence.load_status) << ","
                        << JsonQuote("capture_status") << ":" << JsonQuote(occurrence.capture_status) << ","
                        << JsonQuote("presentation_status") << ":" << JsonQuote(occurrence.presentation_status) << ","
                        << JsonQuote("feature_definition_root_id") << ":" << JsonQuote(occurrence.feature_definition_root_id)
                        << "}\n";
    if (!product_occurrences)
    {
      error = "failed to write output file: " + product_occurrences_path;
      return false;
    }
  }
  if (!FinishStream(product_occurrences, product_occurrences_path, error))
    return false;

  const std::string links_path = output_dir + "\\document_links.jsonl";
  std::ofstream links(links_path.c_str(), std::ios::out | std::ios::binary);
  if (!links)
  {
    error = "failed to open output file: " + links_path;
    return false;
  }
  for (i = 0; i < package.document_graph.links.size(); ++i)
  {
    const DocumentLink& link = package.document_graph.links[i];
    links << "{"
          << JsonQuote("link_id") << ":" << JsonQuote(link.link_id) << ","
          << JsonQuote("from_document_id") << ":" << JsonQuote(link.from_document_id) << ","
          << JsonQuote("to_document_id") << ":" << JsonQuote(link.to_document_id) << ","
          << JsonQuote("reference_id") << ":" << JsonQuote(link.reference_id) << ","
          << JsonQuote("link_role") << ":" << JsonQuote(link.link_role) << ","
          << JsonQuote("link_status") << ":" << JsonQuote(link.link_status) << ","
          << JsonQuote("value_source") << ":" << JsonQuote(link.value_source)
          << "}\n";
    if (!links)
    {
      error = "failed to write output file: " + links_path;
      return false;
    }
  }
  if (!FinishStream(links, links_path, error))
    return false;

  const std::string object_path = output_dir + "\\object_entities.jsonl";
  std::ofstream objects(object_path.c_str(), std::ios::out | std::ios::binary);
  if (!objects)
  {
    error = "failed to open output file: " + object_path;
    return false;
  }
  for (i = 0; i < package.objects.size(); ++i)
  {
    const ObjectEntity& object = package.objects[i];
    objects << "{"
            << JsonQuote("object_id") << ":" << JsonQuote(object.object_id) << ","
            << JsonQuote("document_id") << ":" << JsonQuote(object.document_id) << ","
            << JsonQuote("object_kind") << ":" << JsonQuote(object.object_kind) << ","
            << JsonQuote("display_name") << ":" << JsonQuote(object.display_name) << ","
            << JsonQuote("internal_name") << ":" << JsonQuote(object.internal_name) << ","
            << JsonQuote("startup_type") << ":" << JsonQuote(object.startup_type) << ","
            << JsonQuote("update_status") << ":" << JsonQuote(object.update_status) << ","
            << JsonQuote("supplemental_sources") << ":" << JsonQuote(object.supplemental_sources) << ","
            << JsonQuote("identity") << ":{"
            << JsonQuote("capture_id") << ":" << JsonQuote(object.identity.capture_id) << ","
            << JsonQuote("native_identity") << ":" << JsonQuote(object.identity.native_identity) << ","
            << JsonQuote("identity_method") << ":" << JsonQuote(object.identity.identity_method) << ","
            << JsonQuote("read_status") << ":" << JsonQuote(object.identity.read_status)
            << "},"
            << JsonQuote("capture_status") << ":" << JsonQuote(object.capture_status)
            << "}\n";
    if (!objects)
    {
      error = "failed to write output file: " + object_path;
      return false;
    }
  }
  if (!FinishStream(objects, object_path, error))
    return false;

  const std::string occurrence_path = output_dir + "\\tree_occurrences.jsonl";
  std::ofstream occurrences(occurrence_path.c_str(), std::ios::out | std::ios::binary);
  if (!occurrences)
  {
    error = "failed to open output file: " + occurrence_path;
    return false;
  }
  for (i = 0; i < package.occurrence_graph.object_occurrences.size(); ++i)
  {
    const ObjectOccurrence& occurrence = package.occurrence_graph.object_occurrences[i];
    occurrences << "{"
                << JsonQuote("occurrence_id") << ":" << JsonQuote(occurrence.occurrence_id) << ","
                << JsonQuote("object_id") << ":" << JsonQuote(occurrence.object_id) << ","
                << JsonQuote("parent_occurrence_id") << ":" << JsonQuote(occurrence.parent_occurrence_id) << ","
                << JsonQuote("document_id") << ":" << JsonQuote(occurrence.document_id) << ","
                << JsonQuote("tree_path") << ":" << JsonQuote(occurrence.tree_path) << ","
                << JsonQuote("occurrence_path") << ":" << JsonQuote(occurrence.occurrence_path) << ","
                << JsonQuote("source_index") << ":" << occurrence.source_index << ","
                << JsonQuote("container_index") << ":" << occurrence.container_index << ","
                << JsonQuote("occurrence_role") << ":" << JsonQuote(occurrence.occurrence_role) << ","
                << JsonQuote("enumeration_source") << ":" << JsonQuote(occurrence.enumeration_source) << ","
                << JsonQuote("presentation_status") << ":" << JsonQuote(occurrence.presentation_status) << ","
                << JsonQuote("occurrence_kind") << ":" << JsonQuote(occurrence.occurrence_kind) << ","
                << JsonQuote("product_occurrence_id") << ":" << JsonQuote(occurrence.product_occurrence_id) << ","
                << JsonQuote("reference_id") << ":" << JsonQuote(occurrence.reference_id) << ","
                << JsonQuote("referenced_document_id") << ":" << JsonQuote(occurrence.referenced_document_id) << ","
                << JsonQuote("capture_status") << ":" << JsonQuote(occurrence.capture_status)
                << "}\n";
    if (!occurrences)
    {
      error = "failed to write output file: " + occurrence_path;
      return false;
    }
  }

  if (!FinishStream(occurrences, occurrence_path, error))
    return false;

  const std::string properties_path = output_dir + "\\property_facts.jsonl";
  std::ofstream properties(properties_path.c_str(), std::ios::out | std::ios::binary);
  if (!properties)
  {
    error = "failed to open output file: " + properties_path;
    return false;
  }
  for (i = 0; i < package.properties.size(); ++i)
  {
    const PropertyFact& fact = package.properties[i];
    properties << "{"
               << JsonQuote("property_id") << ":" << JsonQuote(fact.property_id) << ","
               << JsonQuote("subject_id") << ":" << JsonQuote(fact.subject_id) << ","
               << JsonQuote("tab_id") << ":" << JsonQuote(fact.tab_id) << ","
               << JsonQuote("tab_label") << ":" << JsonQuote(fact.tab_label) << ","
               << JsonQuote("group_id") << ":" << JsonQuote(fact.group_id) << ","
               << JsonQuote("group_label") << ":" << JsonQuote(fact.group_label) << ","
               << JsonQuote("key") << ":" << JsonQuote(fact.key) << ","
               << JsonQuote("display_name") << ":" << JsonQuote(fact.display_name) << ","
               << JsonQuote("raw_value") << ":" << JsonQuote(fact.raw_value) << ","
               << JsonQuote("raw_unit") << ":" << JsonQuote(fact.raw_unit) << ","
               << JsonQuote("display_value") << ":" << JsonQuote(fact.display_value) << ","
               << JsonQuote("display_unit") << ":" << JsonQuote(fact.display_unit) << ","
               << JsonQuote("value_type") << ":" << JsonQuote(fact.value_type) << ","
               << JsonQuote("source_api") << ":" << JsonQuote(fact.source_api) << ","
               << JsonQuote("read_status") << ":" << JsonQuote(fact.read_status) << ","
               << JsonQuote("authority") << ":" << JsonQuote(fact.authority) << ","
               << JsonQuote("display_order") << ":" << fact.display_order << ","
               << JsonQuote("read_only") << ":" << (fact.read_only ? "true" : "false")
               << "}\n";
    if (!properties)
    {
      error = "failed to write output file: " + properties_path;
      return false;
    }
  }
  if (!FinishStream(properties, properties_path, error))
    return false;

  const std::string semantic_path = output_dir + "\\semantic_facets.jsonl";
  std::ofstream semantic(semantic_path.c_str(), std::ios::out | std::ios::binary);
  if (!semantic)
  {
    error = "failed to open output file: " + semantic_path;
    return false;
  }
  for (i = 0; i < package.semantic_facets.size(); ++i)
  {
    const SemanticFacet& facet = package.semantic_facets[i];
    semantic << "{"
             << JsonQuote("facet_id") << ":" << JsonQuote(facet.facet_id) << ","
             << JsonQuote("subject_id") << ":" << JsonQuote(facet.subject_id) << ","
             << JsonQuote("facet_kind") << ":" << JsonQuote(facet.facet_kind) << ","
             << JsonQuote("canonical_family") << ":" << JsonQuote(facet.canonical_family) << ","
             << JsonQuote("decoder_id") << ":" << JsonQuote(facet.decoder_id) << ","
             << JsonQuote("decode_level") << ":" << JsonQuote(facet.decode_level) << ","
             << JsonQuote("decode_status") << ":" << JsonQuote(facet.decode_status) << ","
             << JsonQuote("payload_extraction_status") << ":" << JsonQuote(facet.payload_extraction_status) << ","
             << JsonQuote("source_api") << ":" << JsonQuote(facet.source_api) << ","
             << JsonQuote("read_status") << ":" << JsonQuote(facet.read_status)
             << "}\n";
    if (!semantic)
    {
      error = "failed to write output file: " + semantic_path;
      return false;
    }
  }
  if (!FinishStream(semantic, semantic_path, error))
    return false;

  const std::string topology_path = output_dir + "\\topology_entities.jsonl";
  std::ofstream topology(topology_path.c_str(), std::ios::out | std::ios::binary);
  if (!topology)
  {
    error = "failed to open output file: " + topology_path;
    return false;
  }
  for (i = 0; i < package.topology.size(); ++i)
  {
    const TopologyEntity& entity = package.topology[i];
    topology << "{"
             << JsonQuote("topology_id") << ":" << JsonQuote(entity.topology_id) << ","
             << JsonQuote("subject_id") << ":" << JsonQuote(entity.subject_id) << ","
             << JsonQuote("topology_kind") << ":" << JsonQuote(entity.topology_kind) << ","
             << JsonQuote("parent_topology_id") << ":" << JsonQuote(entity.parent_topology_id) << ","
             << JsonQuote("source_kind") << ":" << JsonQuote(entity.source_kind) << ","
             << JsonQuote("value_source") << ":" << JsonQuote(entity.value_source) << ","
             << JsonQuote("stable_id_method") << ":" << JsonQuote(entity.stable_id_method) << ","
             << JsonQuote("stability_scope") << ":" << JsonQuote(entity.stability_scope) << ","
             << JsonQuote("topology_index") << ":" << entity.topology_index << ","
             << JsonQuote("dimension") << ":" << entity.dimension << ","
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
             << JsonQuote("read_status") << ":" << JsonQuote(entity.read_status)
             << "}\n";
    if (!topology)
    {
      error = "failed to write output file: " + topology_path;
      return false;
    }
  }
  if (!FinishStream(topology, topology_path, error))
    return false;

  const std::string geometry_path = output_dir + "\\geometry_entities.jsonl";
  std::ofstream geometry(geometry_path.c_str(), std::ios::out | std::ios::binary);
  if (!geometry)
  {
    error = "failed to open output file: " + geometry_path;
    return false;
  }
  for (i = 0; i < package.geometry.size(); ++i)
  {
    const GeometryEntity& entity = package.geometry[i];
    geometry << "{"
             << JsonQuote("geometry_id") << ":" << JsonQuote(entity.geometry_id) << ","
             << JsonQuote("subject_id") << ":" << JsonQuote(entity.subject_id) << ","
             << JsonQuote("body_topology_id") << ":" << JsonQuote(entity.body_topology_id) << ","
             << JsonQuote("topology_id") << ":" << JsonQuote(entity.topology_id) << ","
             << JsonQuote("geometry_kind") << ":" << JsonQuote(entity.geometry_kind) << ","
             << JsonQuote("value_source") << ":" << JsonQuote(entity.value_source) << ","
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
             << JsonQuote("representation_status") << ":" << JsonQuote(entity.representation_status)
             << "}\n";
    if (!geometry)
    {
      error = "failed to write output file: " + geometry_path;
      return false;
    }
  }
  if (!FinishStream(geometry, geometry_path, error))
    return false;
  return true;
}

bool NormalizedArtifactWriter::Write(const ReconstructionPackage& package,
                                     const CaptureReport& report,
                                     const std::string& output_dir,
                                     bool pretty,
                                     const std::string& legacy_projection_status,
                                     std::string& error)
{
  if (!EnsureDirectory(output_dir, error))
    return false;

  std::ostringstream manifest;
  const std::string nl = NewLine(pretty);
  const std::string i1 = Indent(pretty, 1);
  manifest << "{" << nl
           << i1 << JsonQuote("schema_version") << ":" << (pretty ? " " : "") << JsonQuote("caa_capture_v1") << "," << nl
           << i1 << JsonQuote("parser_version") << ":" << (pretty ? " " : "") << JsonQuote("0.2.0") << "," << nl
           << i1 << JsonQuote("architecture") << ":" << (pretty ? " " : "") << JsonQuote("deep_module_capture") << "," << nl
           << i1 << JsonQuote("document_count") << ":" << (pretty ? " " : "") << report.document_count << "," << nl
           << i1 << JsonQuote("object_count") << ":" << (pretty ? " " : "") << report.object_count << "," << nl
           << i1 << JsonQuote("occurrence_count") << ":" << (pretty ? " " : "") << report.occurrence_count << "," << nl
           << i1 << JsonQuote("product_reference_count") << ":" << (pretty ? " " : "") << static_cast<int>(package.product_references.size()) << "," << nl
           << i1 << JsonQuote("product_occurrence_count") << ":" << (pretty ? " " : "") << static_cast<int>(package.product_occurrences.size()) << "," << nl
           << i1 << JsonQuote("document_link_count") << ":" << (pretty ? " " : "") << static_cast<int>(package.document_graph.links.size()) << "," << nl
           << i1 << JsonQuote("property_count") << ":" << (pretty ? " " : "") << report.property_count << "," << nl
           << i1 << JsonQuote("semantic_facet_count") << ":" << (pretty ? " " : "") << report.semantic_facet_count << "," << nl
           << i1 << JsonQuote("topology_count") << ":" << (pretty ? " " : "") << report.topology_count << "," << nl
           << i1 << JsonQuote("geometry_count") << ":" << (pretty ? " " : "") << report.geometry_count << "," << nl
           << i1 << JsonQuote("selected_reconstruction_route") << ":" << (pretty ? " " : "") << JsonQuote(package.reconstruction_plan) << "," << nl
           << i1 << JsonQuote("capture_status") << ":" << (pretty ? " " : "") << JsonQuote(package.capture_status) << "," << nl
           << i1 << JsonQuote("native_document_open_status") << ":" << (pretty ? " " : "") << JsonQuote(package.document_graph.documents.empty() ? "unavailable" : package.document_graph.documents[0].native_document_open_status) << "," << nl
           << i1 << JsonQuote("legacy_projection_status") << ":" << (pretty ? " " : "") << JsonQuote(legacy_projection_status) << nl
           << "}" << nl;

  std::ostringstream report_json;
  report_json << "{" << nl
              << i1 << JsonQuote("success") << ":" << (pretty ? " " : "") << (report.success ? "true" : "false") << "," << nl
              << i1 << JsonQuote("exit_code") << ":" << (pretty ? " " : "") << report.exit_code << "," << nl
              << i1 << JsonQuote("stage") << ":" << (pretty ? " " : "") << JsonQuote(report.stage) << "," << nl
              << i1 << JsonQuote("message") << ":" << (pretty ? " " : "") << JsonQuote(report.message) << "," << nl
              << i1 << JsonQuote("semantic_facet_count") << ":" << (pretty ? " " : "") << report.semantic_facet_count << "," << nl
              << i1 << JsonQuote("topology_count") << ":" << (pretty ? " " : "") << report.topology_count << "," << nl
              << i1 << JsonQuote("geometry_count") << ":" << (pretty ? " " : "") << report.geometry_count << "," << nl
              << i1 << JsonQuote("diagnostic_count") << ":" << (pretty ? " " : "") << static_cast<int>(report.diagnostics.size()) << nl
              << "}" << nl;

  std::ostringstream plan_json;
  plan_json << "{" << nl
            << i1 << JsonQuote("route") << ":" << (pretty ? " " : "") << JsonQuote(package.reconstruction_plan) << "," << nl
            << i1 << JsonQuote("status") << ":" << (pretty ? " " : "") << JsonQuote("partial_tree_capture") << nl
            << "}" << nl;

  if (!WriteText(output_dir + "\\manifest.json", manifest.str(), error))
    return false;
  if (!WriteText(output_dir + "\\capture_report.json", report_json.str(), error))
    return false;
  if (!WriteText(output_dir + "\\reconstruction_plan.json", plan_json.str(), error))
    return false;
  if (!WriteJsonLines(package, output_dir, error))
    return false;
  return true;
}

}
