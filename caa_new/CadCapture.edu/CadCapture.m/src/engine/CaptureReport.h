#ifndef CADCAPTURE_ENGINE_CAPTUREREPORT_H
#define CADCAPTURE_ENGINE_CAPTUREREPORT_H

#include "model/CaptureStatus.h"
#include <string>
#include <vector>

namespace cadcapture {

struct CaptureReport
{
  int exit_code;
  bool success;
  std::string stage;
  std::string message;
  int document_count;
  int object_count;
  int occurrence_count;
  int property_count;
  std::vector<Diagnostic> diagnostics;

  CaptureReport()
    : exit_code(1),
      success(false),
      document_count(0),
      object_count(0),
      occurrence_count(0),
      property_count(0)
  {
  }

  void AddDiagnostic(const std::string& severity,
                     const std::string& code,
                     const std::string& subject_id,
                     const std::string& text,
                     const std::string& at_stage)
  {
    Diagnostic diagnostic;
    diagnostic.severity = severity;
    diagnostic.code = code;
    diagnostic.subject_id = subject_id;
    diagnostic.message = text;
    diagnostic.stage = at_stage;
    diagnostics.push_back(diagnostic);
  }

  bool HasErrors() const
  {
    size_t i;
    for (i = 0; i < diagnostics.size(); ++i)
    {
      if (diagnostics[i].severity == "error")
        return true;
    }
    return false;
  }
};

}

#endif
