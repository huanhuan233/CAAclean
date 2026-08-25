#ifndef CADCAPTURE_MODEL_CAPTURESTATUS_H
#define CADCAPTURE_MODEL_CAPTURESTATUS_H

#include <string>

namespace cadcapture {

struct Diagnostic
{
  std::string severity;
  std::string code;
  std::string subject_id;
  std::string message;
  std::string stage;

  Diagnostic() : severity("info") {}
};

}

#endif
