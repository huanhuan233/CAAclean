#include "reconstruction/ReconstructionValidator.h"
#include <map>
#include <set>

namespace cadcapture {

static bool HasKey(const std::map<std::string, bool>& values, const std::string& key)
{
  return values.find(key) != values.end();
}

static bool ParentChainHasCycle(const std::string& start_id,
                                const std::map<std::string, std::string>& parent_by_occurrence)
{
  std::set<std::string> seen;
  std::string current = start_id;
  while (!current.empty())
  {
    if (seen.find(current) != seen.end())
      return true;
    seen.insert(current);
    std::map<std::string, std::string>::const_iterator found = parent_by_occurrence.find(current);
    if (found == parent_by_occurrence.end())
      return false;
    current = found->second;
  }
  return false;
}

bool ReconstructionValidator::Validate(const ReconstructionPackage& package, std::string& error) const
{
  size_t i;
  if (package.document_graph.documents.empty())
  {
    error = "package has no document";
    return false;
  }
  std::map<std::string, bool> document_ids;
  for (i = 0; i < package.document_graph.documents.size(); ++i)
  {
    const std::string& document_id = package.document_graph.documents[i].document_id;
    if (document_id.empty())
    {
      error = "document_id is empty";
      return false;
    }
    if (HasKey(document_ids, document_id))
    {
      error = "duplicate document_id: " + document_id;
      return false;
    }
    document_ids[document_id] = true;
  }

  std::map<std::string, bool> object_ids;
  for (i = 0; i < package.objects.size(); ++i)
  {
    const ObjectEntity& object = package.objects[i];
    if (object.object_id.empty())
    {
      error = "object_id is empty";
      return false;
    }
    if (HasKey(object_ids, object.object_id))
    {
      error = "duplicate object_id: " + object.object_id;
      return false;
    }
    if (!HasKey(document_ids, object.document_id))
    {
      error = "object references missing document_id: " + object.document_id;
      return false;
    }
    object_ids[object.object_id] = true;
  }

  std::map<std::string, bool> occurrence_ids;
  std::map<std::string, std::string> parent_by_occurrence;
  std::map<std::string, bool> occurrence_paths;
  std::map<std::string, bool> primary_tree_paths;
  int primary_root_count = 0;
  int document_root_count = 0;
  for (i = 0; i < package.occurrence_graph.object_occurrences.size(); ++i)
  {
    const ObjectOccurrence& occurrence = package.occurrence_graph.object_occurrences[i];
    if (occurrence.occurrence_id.empty())
    {
      error = "occurrence_id is empty";
      return false;
    }
    if (HasKey(occurrence_ids, occurrence.occurrence_id))
    {
      error = "duplicate occurrence_id: " + occurrence.occurrence_id;
      return false;
    }
    if (!HasKey(document_ids, occurrence.document_id))
    {
      error = "occurrence references missing document_id: " + occurrence.document_id;
      return false;
    }
    if (!HasKey(object_ids, occurrence.object_id))
    {
      error = "occurrence references missing object_id: " + occurrence.object_id;
      return false;
    }
    if (occurrence.occurrence_path.empty())
    {
      error = "occurrence_path is empty: " + occurrence.occurrence_id;
      return false;
    }
    if (HasKey(occurrence_paths, occurrence.occurrence_path))
    {
      error = "duplicate occurrence_path: " + occurrence.occurrence_path;
      return false;
    }
    occurrence_ids[occurrence.occurrence_id] = true;
    occurrence_paths[occurrence.occurrence_path] = true;
    parent_by_occurrence[occurrence.occurrence_id] = occurrence.parent_occurrence_id;

    if (occurrence.parent_occurrence_id.empty())
    {
      if (occurrence.occurrence_role == "primary_tree")
        ++primary_root_count;
      if (occurrence.occurrence_role == "supplemental_discovery")
      {
        error = "supplemental_discovery occurrence has no parent: " + occurrence.occurrence_id;
        return false;
      }
    }
    if (occurrence.occurrence_role == "primary_tree")
    {
      if (occurrence.source_index < 0)
      {
        error = "primary_tree source_index is negative: " + occurrence.occurrence_id;
        return false;
      }
      if (HasKey(primary_tree_paths, occurrence.tree_path))
      {
        error = "duplicate primary tree_path: " + occurrence.tree_path;
        return false;
      }
      primary_tree_paths[occurrence.tree_path] = true;
      if (occurrence.parent_occurrence_id.empty())
        ++document_root_count;
    }
  }

  for (i = 0; i < package.occurrence_graph.object_occurrences.size(); ++i)
  {
    const ObjectOccurrence& occurrence = package.occurrence_graph.object_occurrences[i];
    if (!occurrence.parent_occurrence_id.empty() &&
        !HasKey(occurrence_ids, occurrence.parent_occurrence_id))
    {
      error = "occurrence references missing parent_occurrence_id: " + occurrence.parent_occurrence_id;
      return false;
    }
    if (ParentChainHasCycle(occurrence.occurrence_id, parent_by_occurrence))
    {
      error = "occurrence parent cycle detected at: " + occurrence.occurrence_id;
      return false;
    }
  }

  if (primary_root_count > 1)
  {
    error = "primary_tree has multiple root occurrences";
    return false;
  }

  for (i = 0; i < package.document_graph.documents.size(); ++i)
  {
    if (package.document_graph.documents[i].document_kind == "catpart" && document_root_count != 1)
    {
      error = "CATPart document does not have exactly one document root";
      return false;
    }
  }

  if (package.reconstruction_plan.empty())
  {
    error = "reconstruction route is empty";
    return false;
  }
  for (i = 0; i < package.diagnostics.size(); ++i)
  {
    if (package.diagnostics[i].severity.empty() || package.diagnostics[i].message.empty())
    {
      error = "diagnostic is missing severity or message";
      return false;
    }
  }
  return true;
}

}
