#ifndef CAD_PARSE_IR_H
#define CAD_PARSE_IR_H

#include "CadParseContracts.h"

namespace cadparse
{
class JsonArtifactWriter : public IArtifactWriter
{
public:
  explicit JsonArtifactWriter(bool pretty);

  bool Write(const std::vector<FeatureRecord>& features,
             const std::vector<RelationRecord>& relations,
             const ParseContext& context,
             const std::string& output_dir,
             std::string& error);

private:
  bool _pretty;
};
}

#endif
