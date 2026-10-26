/* 声明采集总入口，连接请求、采集策略、纯数据包与执行报告。 */
#ifndef CADCAPTURE_ENGINE_MODELCAPTUREENGINE_H
#define CADCAPTURE_ENGINE_MODELCAPTUREENGINE_H

#include "engine/CapturePolicy.h"
#include "engine/CaptureReport.h"
#include "engine/CaptureRequest.h"
#include "model/ReconstructionPackage.h"
#include <string>

namespace cadcapture {

/* 统一管理一次采集流程，具体 SDK 读取由各采集器封装。 */
class ModelCaptureEngine
{
public:
  /* 返回是否完成指定模式的执行，失败原因同时写入 error 和报告。 */
  bool Capture(const CaptureRequest& request,
               const CapturePolicy& policy,
               ReconstructionPackage& package,
               CaptureReport& report,
               std::string& error);
};

}

#endif
