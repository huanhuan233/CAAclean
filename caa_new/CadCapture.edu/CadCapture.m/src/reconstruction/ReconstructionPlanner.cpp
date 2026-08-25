#include "reconstruction/ReconstructionPlanner.h"

namespace cadcapture {

bool ReconstructionPlanner::Plan(ReconstructionPackage& package)
{
  if (!package.geometry.empty())
    package.reconstruction_plan = "exact_brep";
  else if (!package.document_graph.documents.empty() ||
           !package.properties.empty() ||
           !package.occurrence_graph.object_occurrences.empty())
    package.reconstruction_plan = "tree_properties";
  else
    package.reconstruction_plan = "opaque_preservation";
  return true;
}

}
