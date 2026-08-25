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

static Diagnostic MakeDiagnostic(const std::string& severity,
                                 const std::string& code,
                                 const std::string& subject_id,
                                 const std::string& message,
                                 const std::string& stage)
{
  Diagnostic diagnostic;
  diagnostic.severity = severity;
  diagnostic.code = code;
  diagnostic.subject_id = subject_id;
  diagnostic.message = message;
  diagnostic.stage = stage;
  return diagnostic;
}

}

#endif
