/* 定义一次采集请求的输入输出路径、自检模式和格式选项。 */
#ifndef CADCAPTURE_ENGINE_CAPTUREREQUEST_H
#define CADCAPTURE_ENGINE_CAPTUREREQUEST_H

#include <string>

namespace cadcapture {

/* 请求只携带选项，不持有 CATIA 文档或原生接口。 */
struct CaptureRequest
{
  std::string input_path;
  std::string output_dir;
  bool self_test;
  bool probe_runtime;
  bool pretty;

  /* 默认关闭自检、运行时探测和美化输出，由命令行显式开启。 */
  CaptureRequest()
    : self_test(false), probe_runtime(false), pretty(false)
  {
  }
};

}

#endif
