#ifndef CADCAPTURE_ENGINE_CAPTUREREQUEST_H
#define CADCAPTURE_ENGINE_CAPTUREREQUEST_H

#include <string>

namespace cadcapture {

struct CaptureRequest
{
  std::string input_path;
  std::string output_dir;
  bool self_test;
  bool probe_runtime;
  bool pretty;

  CaptureRequest()
    : self_test(false), probe_runtime(false), pretty(false)
  {
  }
};

}

#endif
