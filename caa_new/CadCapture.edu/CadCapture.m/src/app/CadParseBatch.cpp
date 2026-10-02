#include "engine/CapturePolicy.h"
#include "engine/CaptureRequest.h"
#include "engine/ModelCaptureEngine.h"
#include "platform/WindowsPathCodec.h"
#include <iostream>
#include <string>
#include <vector>
#include <windows.h>
#include <shellapi.h>

#pragma comment(lib, "shell32.lib")

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

// 中文：内部参数统一为 UTF-8；调用器 x86/x64 均可传同一条宽字符 Windows 命令行。
static bool ParseArgs(const std::vector<std::string>& args, CaptureRequest& request)
{
  size_t i;
  for (i = 1; i < args.size(); ++i)
  {
    const std::string& arg = args[i];
    if (arg == "--self-test")
      request.self_test = true;
    else if (arg == "--probe-runtime")
      request.probe_runtime = true;
    else if (arg == "--pretty")
      request.pretty = true;
    else if (arg == "--input" && i + 1 < args.size())
      request.input_path = args[++i];
    else if (arg == "--output" && i + 1 < args.size())
      request.output_dir = args[++i];
    else
      return false;
  }
  return true;
}

int main(int argc, char** argv)
{
  // 中文：不使用受控制台代码页影响的 argv；GetCommandLineW 对两种目标位数行为相同。
  (void)argc;
  (void)argv;
  int wide_count = 0;
  LPWSTR* wide_args = CommandLineToArgvW(GetCommandLineW(), &wide_count);
  if (!wide_args) return 2;
  std::vector<std::string> args;
  for (int i = 0; i < wide_count; ++i)
  {
    const std::string encoded = cadcapture::WindowsPathCodec::Encode(wide_args[i]);
    if (encoded.empty())
    {
      LocalFree(wide_args);
      return 2;
    }
    args.push_back(encoded);
  }
  LocalFree(wide_args);
  CaptureRequest request;
  if (args.size() < 2 || !ParseArgs(args, request))
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
