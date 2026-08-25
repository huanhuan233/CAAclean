#ifndef CADCAPTURE_RECONSTRUCTION_RECONSTRUCTIONPLANNER_H
#define CADCAPTURE_RECONSTRUCTION_RECONSTRUCTIONPLANNER_H

#include "model/ReconstructionPackage.h"

namespace cadcapture {

class ReconstructionPlanner
{
public:
  bool Plan(ReconstructionPackage& package);
};

struct ReconstructionCompleteness
{
  bool has_body;
  bool has_face;
  bool has_edge;
  bool has_vertex;
  bool has_boundary;
  bool has_wire_or_coedge;
  bool has_exact_surface_or_curve;
  bool has_tessellation_coordinates;
  bool has_tree_or_properties;
  bool has_topology_integrity_error;

  ReconstructionCompleteness();
  bool SupportsExactBrep() const;
  bool SupportsTessellation() const;
};

class ReconstructionCompletenessEvaluator
{
public:
  ReconstructionCompleteness Evaluate(const ReconstructionPackage& package) const;
};

}

#endif
