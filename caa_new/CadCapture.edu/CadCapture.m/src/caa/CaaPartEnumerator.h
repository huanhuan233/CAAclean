#ifndef CADCAPTURE_CAA_CAAPARTENUMERATOR_H
#define CADCAPTURE_CAA_CAAPARTENUMERATOR_H

#include "caa/CaaDocumentHandle.h"
#include "model/CaptureIdRegistry.h"
#include "model/ReconstructionPackage.h"
#include <string>
#include <vector>

namespace cadcapture {

struct PartDefinition
{
  std::string document_id;
  std::vector<ObjectOccurrence> occurrence_templates;
};

struct ProjectionContext
{
  std::string parent_occurrence_id;
  std::string tree_path_prefix;
  std::string occurrence_path_prefix;
  std::string product_occurrence_id;
  std::string reference_id;
  std::string referenced_document_id;
};

class CaaPartEnumerator
{
public:
  bool Enumerate(CaaDocumentHandle& document_handle,
                 CaptureIdRegistry& ids,
                 ReconstructionPackage& package,
                 std::string& error);

  bool CaptureDefinition(CaaDocumentHandle& document_handle,
                         CaptureIdRegistry& ids,
                         PartDefinition& definition,
                         ReconstructionPackage& package,
                         std::string& error);

  bool ProjectDefinition(const PartDefinition& definition,
                         const ProjectionContext& context,
                         CaptureIdRegistry& ids,
                         ReconstructionPackage& package,
                         std::string& error);
};

}

#endif
