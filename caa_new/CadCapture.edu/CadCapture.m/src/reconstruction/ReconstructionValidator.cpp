#include "reconstruction/ReconstructionValidator.h"

namespace cadcapture {

static bool HasObjectId(const ReconstructionPackage& package, const std::string& object_id)
{
  size_t i;
  for (i = 0; i < package.objects.size(); ++i)
  {
    if (package.objects[i].object_id == object_id)
      return true;
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
  for (i = 0; i < package.occurrence_graph.object_occurrences.size(); ++i)
  {
    if (!HasObjectId(package, package.occurrence_graph.object_occurrences[i].object_id))
    {
      error = "occurrence references missing object_id: " + package.occurrence_graph.object_occurrences[i].object_id;
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
