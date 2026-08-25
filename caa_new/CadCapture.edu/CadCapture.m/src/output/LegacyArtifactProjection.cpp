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
  if (!FinishLegacyStream(relations, relations_path, error))
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
  return true;
}

}
