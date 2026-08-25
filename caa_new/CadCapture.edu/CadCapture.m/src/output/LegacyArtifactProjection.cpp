#include "output/LegacyArtifactProjection.h"
#include "output/JsonSupport.h"
#include <fstream>

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

bool LegacyArtifactProjection::Write(const ReconstructionPackage& package,
                                     const std::string& output_dir,
                                     std::string& error) const
{
  std::string features;
  size_t i;
  for (i = 0; i < package.objects.size(); ++i)
  {
    const ObjectEntity& object = package.objects[i];
    features += "{";
    features += JsonQuote("feature_id") + ":" + JsonQuote(object.object_id) + ",";
    features += JsonQuote("display_name") + ":" + JsonQuote(object.display_name) + ",";
    features += JsonQuote("internal_name") + ":" + JsonQuote(object.internal_name) + ",";
    features += JsonQuote("startup_type") + ":" + JsonQuote(object.startup_type) + ",";
    features += JsonQuote("update_status") + ":" + JsonQuote(object.update_status) + ",";
    features += JsonQuote("decode_status") + ":" + JsonQuote(object.capture_status);
    features += "}\n";
  }

  std::string relations;
  for (i = 0; i < package.occurrence_graph.object_occurrences.size(); ++i)
  {
    const ObjectOccurrence& occurrence = package.occurrence_graph.object_occurrences[i];
    if (occurrence.parent_occurrence_id.empty())
      continue;
    relations += "{";
    relations += JsonQuote("kind") + ":" + JsonQuote("tree_parent") + ",";
    relations += JsonQuote("from_id") + ":" + JsonQuote(occurrence.parent_occurrence_id) + ",";
    relations += JsonQuote("to_id") + ":" + JsonQuote(occurrence.occurrence_id) + ",";
    relations += JsonQuote("object_id") + ":" + JsonQuote(occurrence.object_id);
    relations += "}\n";
  }

  if (!WriteLegacyText(output_dir + "\\features.jsonl", features, error))
    return false;
  if (!WriteLegacyText(output_dir + "\\relations.jsonl", relations, error))
    return false;
  return true;
}

}
