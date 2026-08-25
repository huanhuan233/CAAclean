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
