#include "CadParseCAA.h"
#include "CadParseIR.h"

#include <iostream>
#include <windows.h>

namespace cadparse
{
struct BatchOptions
{
  BatchOptions() : pretty(false), self_test(false) {}
  std::string input;
  std::string output;
  bool pretty;
  bool self_test;
};

static bool ParseArguments(int argc, char** argv, BatchOptions& options, std::string& error)
{
  int i = 1;
  for (; i < argc; ++i)
  {
    const std::string argument = argv[i];
    if (argument == "--input" && i + 1 < argc) options.input = argv[++i];
    else if (argument == "--output" && i + 1 < argc) options.output = argv[++i];
    else if (argument == "--pretty") options.pretty = true;
    else if (argument == "--read-only") {}
    else if (argument == "--self-test") options.self_test = true;
    else
    {
      error = std::string("unknown or incomplete argument: ") + argument;
      return false;
    }
  }
  if (!options.self_test && (options.input.empty() || options.output.empty()))
  {
    error = "--input and --output are required";
    return false;
  }
  return true;
}
}

static int RunBatch(int argc, char** argv)
{
  using namespace cadparse;
  BatchOptions options;
  std::string error;
  if (!ParseArguments(argc, argv, options, error))
  {
    std::cerr << error << std::endl;
    std::cerr << "usage: CadParseMvp --input <file.CATPart> --output <directory> [--read-only] [--pretty]"
              << std::endl;
    return 2;
  }
  if (options.self_test)
  {
    SelfTestSuite suite;
    const int failures = suite.RunAll();
    if (failures)
    {
      std::cerr << "self-test failures: " << failures << std::endl;
      return 1;
    }
    std::cout << "self-test passed" << std::endl;
    return 0;
  }

  const DWORD total_start = GetTickCount();
  ParseContext context;
  context.runtime_info["catia_release"] = "V5R21";
  // TODO(R21_API_VERIFY): no verified Public API for installed SP/HF was found locally.
  context.runtime_info["service_pack"] = "unknown";
  context.runtime_info["hot_fix"] = "unknown";
  context.runtime_info["platform"] = "Win32/x86";

  SessionGuard session;
  if (!session.Open(error))
  {
    std::cerr << error << std::endl;
    return 10;
  }

  const DWORD open_start = GetTickCount();
  DocumentGuard document;
  if (!document.OpenReadOnly(options.input, error))
  {
    std::cerr << error << std::endl;
    return 11;
  }
  context.statistics.document_open_ms = static_cast<long>(GetTickCount() - open_start);

  FeatureTypeRegistry registry;
  std::vector<IFeatureDecoder*> decoders;
  RegisterCoreDecoders(registry, decoders);
  std::vector<FeatureRecord> features;
  std::vector<RelationRecord> relations;

  const DWORD traversal_start = GetTickCount();
  UniversalFeatureCrawler crawler(registry, context, features, relations);
  if (!crawler.Crawl(document.Get(), error))
  {
    DeleteCoreDecoders(decoders);
    std::cerr << error << std::endl;
    return 12;
  }
  context.statistics.traversal_ms = static_cast<long>(GetTickCount() - traversal_start);
  DeleteCoreDecoders(decoders);

  if (!CoverageTracker::Validate(context.statistics))
  {
    std::cerr << "coverage conservation failed" << std::endl;
    return 13;
  }

  JsonArtifactWriter writer(options.pretty);
  const DWORD output_start = GetTickCount();
  context.statistics.total_ms = static_cast<long>(GetTickCount() - total_start);
  if (!writer.Write(features, relations, context, options.output, error))
  {
    std::cerr << error << std::endl;
    return 14;
  }
  context.statistics.output_ms = static_cast<long>(GetTickCount() - output_start);
  context.statistics.total_ms = static_cast<long>(GetTickCount() - total_start);
  if (!writer.Write(features, relations, context, options.output, error))
  {
    std::cerr << error << std::endl;
    return 14;
  }

  std::cout << "parsed " << features.size() << " objects; output=" << options.output << std::endl;
  return 0;
}

int main(int argc, char** argv)
{
  try
  {
    return RunBatch(argc, argv);
  }
  catch (...)
  {
    std::cerr << "unhandled CAA/native exception at batch boundary" << std::endl;
    return 15;
  }
}
