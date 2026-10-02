#include "reconstruction/ReconstructionPlanner.h"
#include "reconstruction/BrepCompleteness.h"
#include "model/CaptureEvidenceSummary.h"
#include <sstream>

namespace cadcapture {

ReconstructionCompleteness::ReconstructionCompleteness()
  : body_count(0),
    exact_body_count(0),
    incomplete_body_count(0),
    has_tessellation_coordinates(false),
    has_tree_or_properties(false)
{
}

bool ReconstructionCompleteness::SupportsExactBrep() const
{
  return body_count > 0 && exact_body_count == body_count;
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
  const BrepCompleteness brep = BrepCompletenessEvaluator().Evaluate(package);
  completeness.body_count = brep.bodies.size();
  completeness.exact_body_count = brep.exact_body_count;
  completeness.incomplete_body_count = brep.incomplete_body_count;
  completeness.has_tessellation_coordinates = CaptureEvidenceSummary::HasMesh(package);
  return completeness;
}

// 中文：逐体结果控制整包路线；混合体只留部分精确证据，不宣称整包 exact_brep。
bool ReconstructionPlanner::Plan(ReconstructionPackage& package)
{
  ReconstructionCompletenessEvaluator evaluator;
  const ReconstructionCompleteness completeness = evaluator.Evaluate(package);
  package.exact_brep_body_count = completeness.exact_body_count;
  package.incomplete_brep_body_count = completeness.incomplete_body_count;
  if (completeness.SupportsExactBrep())
    package.reconstruction_plan = "exact_brep";
  else if (completeness.SupportsTessellation())
    package.reconstruction_plan = "tessellation";
  else if (completeness.has_tree_or_properties)
    package.reconstruction_plan = "tree_properties";
  else
    package.reconstruction_plan = "opaque_preservation";
  if (completeness.body_count > 0 && completeness.incomplete_body_count > 0)
  {
    std::ostringstream message;
    message << "Exact B-Rep evidence is incomplete for " << completeness.incomplete_body_count
            << " of " << completeness.body_count << " bodies";
    package.diagnostics.push_back(MakeDiagnostic("info", "exact_brep_partial", "reconstruction",
                                                 message.str(), "reconstruction_planner"));
  }
  return true;
}

}
