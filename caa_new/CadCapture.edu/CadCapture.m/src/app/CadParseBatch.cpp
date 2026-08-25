#include "engine/CapturePolicy.h"
#include "engine/CaptureRequest.h"
#include "engine/ModelCaptureEngine.h"
#include <iostream>
#include <string>

using cadcapture::CapturePolicy;
using cadcapture::CaptureReport;
using cadcapture::CaptureRequest;
using cadcapture::ModelCaptureEngine;
using cadcapture::ReconstructionPackage;

static void PrintUsage()
{
  std::cout << "CadCapture --self-test\n";
  std::cout << "CadCapture --probe-runtime\n";
  std::cout << "CadCapture --input <file.CATPart|file.CATProduct> --output <directory> [--pretty]\n";
}

static bool ParseArgs(int argc, char** argv, CaptureRequest& request)
{
  int i;
  for (i = 1; i < argc; ++i)
  {
    const std::string arg = argv[i];
    if (arg == "--self-test")
      request.self_test = true;
    else if (arg == "--probe-runtime")
      request.probe_runtime = true;
    else if (arg == "--pretty")
      request.pretty = true;
    else if (arg == "--input" && i + 1 < argc)
      request.input_path = argv[++i];
    else if (arg == "--output" && i + 1 < argc)
      request.output_dir = argv[++i];
    else
      return false;
  }
  return true;
}

int main(int argc, char** argv)
{
  CaptureRequest request;
  if (argc < 2 || !ParseArgs(argc, argv, request))
  {
    PrintUsage();
    return 2;
  }

  CapturePolicy policy;
  ReconstructionPackage package;
  CaptureReport report;
  std::string error;
  ModelCaptureEngine engine;
  const bool ok = engine.Capture(request, policy, package, report, error);

  if (!ok)
  {
    if (!error.empty())
      std::cerr << error << "\n";
    PrintUsage();
    return report.exit_code;
  }

  std::cout << report.message << "\n";
  std::cout << "documents=" << report.document_count
            << " objects=" << report.object_count
            << " occurrences=" << report.occurrence_count
            << " properties=" << report.property_count << "\n";
  return report.exit_code;
}
