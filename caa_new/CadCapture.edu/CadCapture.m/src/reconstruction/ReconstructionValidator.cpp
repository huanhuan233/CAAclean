#include "reconstruction/ReconstructionValidator.h"
#include <float.h>
#include <map>
#include <sstream>
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

static bool IsFiniteDouble(double value)
{
  return _finite(value) != 0;
}

static bool ValidateTransform(const ProductOccurrence& occurrence, std::string& error)
{
  if (occurrence.transform_4x4.size() != 16)
  {
    error = "product transform does not contain 16 values: " + occurrence.occurrence_id;
    return false;
  }
  size_t i;
  for (i = 0; i < occurrence.transform_4x4.size(); ++i)
  {
    if (!IsFiniteDouble(occurrence.transform_4x4[i]))
    {
      error = "product transform contains non-finite value: " + occurrence.occurrence_id;
      return false;
    }
  }
  if (occurrence.depth > 0 && occurrence.transform_status == "identity_root")
  {
    error = "non-root product occurrence cannot use identity_root transform status: " + occurrence.occurrence_id;
    return false;
  }
  if (occurrence.depth > 0 && occurrence.transform_status == "resolved_absolute" &&
      occurrence.transform_source.empty())
  {
    error = "resolved product transform is missing source: " + occurrence.occurrence_id;
    return false;
  }
  return true;
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

  std::map<std::string, bool> reference_ids;
  for (i = 0; i < package.product_references.size(); ++i)
  {
    const ProductReferenceEntity& reference = package.product_references[i];
    if (reference.reference_id.empty())
    {
      error = "product reference_id is empty";
      return false;
    }
    if (HasKey(reference_ids, reference.reference_id))
    {
      error = "duplicate product reference_id: " + reference.reference_id;
      return false;
    }
    if (!reference.referenced_document_id.empty() &&
        !HasKey(document_ids, reference.referenced_document_id))
    {
      error = "product reference points to missing document_id: " + reference.referenced_document_id;
      return false;
    }
    reference_ids[reference.reference_id] = true;
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

  std::map<std::string, bool> product_paths;
  int product_root_count = 0;
  for (i = 0; i < package.product_occurrences.size(); ++i)
  {
    const ProductOccurrence& occurrence = package.product_occurrences[i];
    if (occurrence.occurrence_id.empty())
    {
      error = "product occurrence_id is empty";
      return false;
    }
    if (HasKey(occurrence_ids, occurrence.occurrence_id))
    {
      error = "duplicate occurrence_id across product/object nodes: " + occurrence.occurrence_id;
      return false;
    }
    if (!HasKey(reference_ids, occurrence.reference_id))
    {
      error = "product occurrence references missing reference_id: " + occurrence.reference_id;
      return false;
    }
    if (!occurrence.referenced_document_id.empty() &&
        !HasKey(document_ids, occurrence.referenced_document_id))
    {
      error = "product occurrence references missing document_id: " + occurrence.referenced_document_id;
      return false;
    }
    if (occurrence.occurrence_path.empty())
    {
      error = "product occurrence_path is empty: " + occurrence.occurrence_id;
      return false;
    }
    if (HasKey(occurrence_paths, occurrence.occurrence_path) ||
        HasKey(product_paths, occurrence.occurrence_path))
    {
      error = "duplicate product occurrence_path: " + occurrence.occurrence_path;
      return false;
    }
    if (occurrence.source_index < 0)
    {
      error = "product source_index is negative: " + occurrence.occurrence_id;
      return false;
    }
    if (!ValidateTransform(occurrence, error))
      return false;
    product_paths[occurrence.occurrence_path] = true;
    occurrence_ids[occurrence.occurrence_id] = true;
    parent_by_occurrence[occurrence.occurrence_id] = occurrence.parent_occurrence_id;
    if (occurrence.parent_occurrence_id.empty())
      ++product_root_count;
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
  for (i = 0; i < package.product_occurrences.size(); ++i)
  {
    const ProductOccurrence& occurrence = package.product_occurrences[i];
    if (!occurrence.parent_occurrence_id.empty() &&
        !HasKey(occurrence_ids, occurrence.parent_occurrence_id))
    {
      error = "product occurrence references missing parent_occurrence_id: " + occurrence.parent_occurrence_id;
      return false;
    }
    if (ParentChainHasCycle(occurrence.occurrence_id, parent_by_occurrence))
    {
      error = "mixed occurrence parent cycle detected at: " + occurrence.occurrence_id;
      return false;
    }
  }

  if (product_root_count > 1)
  {
    error = "product tree has multiple root product occurrences";
    return false;
  }

  if (package.product_occurrences.empty() && primary_root_count > 1)
  {
    error = "primary_tree has multiple root occurrences";
    return false;
  }

  for (i = 0; i < package.document_graph.documents.size(); ++i)
  {
    if (package.product_occurrences.empty() &&
        package.document_graph.documents[i].document_kind == "catpart" && document_root_count != 1)
    {
      error = "CATPart document does not have exactly one document root";
      return false;
    }
  }

  for (i = 0; i < package.document_graph.links.size(); ++i)
  {
    const DocumentLink& link = package.document_graph.links[i];
    if (!HasKey(document_ids, link.from_document_id) ||
        (!link.to_document_id.empty() && !HasKey(document_ids, link.to_document_id)))
    {
      error = "document link has dangling endpoint: " + link.link_id;
      return false;
    }
    if (!link.reference_id.empty() && !HasKey(reference_ids, link.reference_id))
    {
      error = "document link references missing reference_id: " + link.reference_id;
      return false;
    }
  }

  std::map<std::string, bool> property_ids;
  for (i = 0; i < package.properties.size(); ++i)
  {
    const PropertyFact& fact = package.properties[i];
    if (fact.property_id.empty())
    {
      error = "property_id is empty";
      return false;
    }
    if (HasKey(property_ids, fact.property_id))
    {
      error = "duplicate property_id: " + fact.property_id;
      return false;
    }
    if (!HasKey(document_ids, fact.subject_id) &&
        !HasKey(object_ids, fact.subject_id) &&
        !HasKey(occurrence_ids, fact.subject_id) &&
        !HasKey(reference_ids, fact.subject_id))
    {
      error = "property references missing subject_id: " + fact.subject_id;
      return false;
    }
    if (fact.tab_id.empty() || fact.group_id.empty() || fact.key.empty())
    {
      error = "property is missing tab/group/key: " + fact.property_id;
      return false;
    }
    property_ids[fact.property_id] = true;
  }

  std::map<std::string, bool> semantic_facet_ids;
  for (i = 0; i < package.semantic_facets.size(); ++i)
  {
    const SemanticFacet& facet = package.semantic_facets[i];
    if (facet.facet_id.empty())
    {
      error = "semantic facet_id is empty";
      return false;
    }
    if (HasKey(semantic_facet_ids, facet.facet_id))
    {
      error = "duplicate semantic facet_id: " + facet.facet_id;
      return false;
    }
    if (!HasKey(document_ids, facet.subject_id) &&
        !HasKey(object_ids, facet.subject_id) &&
        !HasKey(occurrence_ids, facet.subject_id) &&
        !HasKey(reference_ids, facet.subject_id))
    {
      error = "semantic facet references missing subject_id: " + facet.subject_id;
      return false;
    }
    if (facet.facet_kind.empty() ||
        facet.canonical_family.empty() ||
        facet.decoder_id.empty() ||
        facet.decode_level.empty() ||
        facet.decode_status.empty() ||
        facet.payload_extraction_status.empty())
    {
      error = "semantic facet missing required classification fields: " + facet.facet_id;
      return false;
    }
    semantic_facet_ids[facet.facet_id] = true;
  }

  std::map<std::string, bool> topology_ids;
  for (i = 0; i < package.topology.size(); ++i)
  {
    const TopologyEntity& entity = package.topology[i];
    if (entity.topology_id.empty())
    {
      error = "topology_id is empty";
      return false;
    }
    if (HasKey(topology_ids, entity.topology_id))
    {
      error = "duplicate topology_id: " + entity.topology_id;
      return false;
    }
    if (!HasKey(document_ids, entity.subject_id) &&
        !HasKey(object_ids, entity.subject_id) &&
        !HasKey(occurrence_ids, entity.subject_id) &&
        !HasKey(reference_ids, entity.subject_id))
    {
      error = "topology references missing subject_id: " + entity.subject_id;
      return false;
    }
    if (entity.topology_kind.empty() || entity.read_status.empty())
    {
      error = "topology entity missing kind/status: " + entity.topology_id;
      return false;
    }
    topology_ids[entity.topology_id] = true;
  }
  for (i = 0; i < package.topology.size(); ++i)
  {
    const TopologyEntity& entity = package.topology[i];
    if (!entity.parent_topology_id.empty() &&
        !HasKey(topology_ids, entity.parent_topology_id))
    {
      error = "topology references missing parent_topology_id: " + entity.parent_topology_id;
      return false;
    }
  }

  std::map<std::string, bool> geometry_ids;
  for (i = 0; i < package.geometry.size(); ++i)
  {
    const GeometryEntity& entity = package.geometry[i];
    if (entity.geometry_id.empty())
    {
      error = "geometry_id is empty";
      return false;
    }
    if (HasKey(geometry_ids, entity.geometry_id))
    {
      error = "duplicate geometry_id: " + entity.geometry_id;
      return false;
    }
    if (!HasKey(document_ids, entity.subject_id) &&
        !HasKey(object_ids, entity.subject_id) &&
        !HasKey(occurrence_ids, entity.subject_id) &&
        !HasKey(reference_ids, entity.subject_id))
    {
      error = "geometry references missing subject_id: " + entity.subject_id;
      return false;
    }
    if (!entity.body_topology_id.empty() &&
        !HasKey(topology_ids, entity.body_topology_id))
    {
      error = "geometry references missing body_topology_id: " + entity.body_topology_id;
      return false;
    }
    if (!entity.topology_id.empty() &&
        !HasKey(topology_ids, entity.topology_id))
    {
      error = "geometry references missing topology_id: " + entity.topology_id;
      return false;
    }
    if (entity.geometry_kind.empty() || entity.representation_status.empty())
    {
      error = "geometry entity missing kind/status: " + entity.geometry_id;
      return false;
    }
    geometry_ids[entity.geometry_id] = true;
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
