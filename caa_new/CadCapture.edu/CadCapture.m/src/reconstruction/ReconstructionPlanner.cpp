#include "reconstruction/ReconstructionPlanner.h"

namespace cadcapture {

ReconstructionCompleteness::ReconstructionCompleteness()
  : has_body(false),
    has_face(false),
    has_edge(false),
    has_vertex(false),
    has_boundary(false),
    has_wire_or_coedge(false),
    has_exact_surface_or_curve(false),
    has_tessellation_coordinates(false),
    has_tree_or_properties(false),
    has_topology_integrity_error(false)
{
}

bool ReconstructionCompleteness::SupportsExactBrep() const
{
  return has_body &&
         has_face &&
         has_edge &&
         has_vertex &&
         has_boundary &&
         has_wire_or_coedge &&
         has_exact_surface_or_curve &&
         !has_topology_integrity_error;
}

bool ReconstructionCompleteness::SupportsTessellation() const
{
  return has_tessellation_coordinates && !SupportsExactBrep();
}

ReconstructionCompleteness ReconstructionCompletenessEvaluator::Evaluate(const ReconstructionPackage& package) const
{
  ReconstructionCompleteness completeness;
  completeness.has_tree_or_properties = !package.document_graph.documents.empty() ||
                                        !package.properties.empty() ||
                                        !package.occurrence_graph.object_occurrences.empty();

  size_t i;
  for (i = 0; i < package.topology.size(); ++i)
  {
    const TopologyEntity& entity = package.topology[i];
    if (entity.topology_kind == "body")
      completeness.has_body = true;
    else if (entity.topology_kind == "face")
      completeness.has_face = true;
    else if (entity.topology_kind == "edge")
      completeness.has_edge = true;
    else if (entity.topology_kind == "vertex")
      completeness.has_vertex = true;
    else if (entity.topology_kind == "wire" || entity.topology_kind == "coedge")
      completeness.has_wire_or_coedge = true;
    if (entity.geometry_status == "exact_surface" ||
        entity.geometry_status == "exact_curve" ||
        entity.geometry_status == "exact")
      completeness.has_exact_surface_or_curve = true;
    if (entity.read_status == "integrity_error" ||
        entity.measure_status == "integrity_error" ||
        entity.geometry_status == "integrity_error")
      completeness.has_topology_integrity_error = true;
  }

  for (i = 0; i < package.topology_relations.size(); ++i)
  {
    const TopologyRelation& relation = package.topology_relations[i];
    if (relation.relation_kind == "boundary" ||
        relation.relation_kind == "outer_loop" ||
        relation.relation_kind == "inner_loop" ||
        relation.relation_kind == "adjacent_to" ||
        relation.relation_kind == "previous" ||
        relation.relation_kind == "next")
      completeness.has_boundary = true;
    if (relation.relation_kind == "wire_coedge" ||
        relation.relation_kind == "coedge_edge" ||
        relation.relation_kind == "previous" ||
        relation.relation_kind == "next")
      completeness.has_wire_or_coedge = true;
    if (relation.read_status == "integrity_error")
      completeness.has_topology_integrity_error = true;
  }

  for (i = 0; i < package.geometry.size(); ++i)
  {
    const GeometryEntity& entity = package.geometry[i];
    if (entity.representation_status == "coordinates_available" ||
        entity.representation_status == "triangles_available")
      completeness.has_tessellation_coordinates = true;
    if (entity.geometry_kind == "surface" ||
        entity.geometry_kind == "curve")
    {
      if (entity.representation_status == "exact" ||
          entity.representation_status == "native_exact")
        completeness.has_exact_surface_or_curve = true;
    }
  }

  for (i = 0; i < package.diagnostics.size(); ++i)
  {
    const Diagnostic& diagnostic = package.diagnostics[i];
    if (diagnostic.severity == "error" &&
        (diagnostic.stage == "topology" || diagnostic.code.find("TOPOLOGY") != std::string::npos))
      completeness.has_topology_integrity_error = true;
  }

  return completeness;
}

bool ReconstructionPlanner::Plan(ReconstructionPackage& package)
{
  ReconstructionCompletenessEvaluator evaluator;
  const ReconstructionCompleteness completeness = evaluator.Evaluate(package);
  if (completeness.SupportsExactBrep())
    package.reconstruction_plan = "exact_brep";
  else if (completeness.SupportsTessellation())
    package.reconstruction_plan = "tessellation";
  else if (completeness.has_tree_or_properties)
    package.reconstruction_plan = "tree_properties";
  else
    package.reconstruction_plan = "opaque_preservation";
  return true;
}

}
