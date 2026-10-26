/* 声明规范化采集清单、报告和实体文件的写出接口。 */
#ifndef CADCAPTURE_OUTPUT_NORMALIZEDARTIFACTWRITER_H
#define CADCAPTURE_OUTPUT_NORMALIZEDARTIFACTWRITER_H

#include "engine/CaptureReport.h"
#include "model/ReconstructionPackage.h"
#include <string>

namespace cadcapture {

/* 序列化规范化模型和报告；仅负责写文件，目录所有权与提交由仓储负责。 */
class NormalizedArtifactWriter
{
public:
  /* 写清单、报告、重建计划和实体流；pretty 仅影响普通 JSON，JSONL 保持每条一行。 */
  bool Write(const ReconstructionPackage& package,
             const CaptureReport& report,
             const std::string& output_dir,
             bool pretty,
             const std::string& legacy_projection_status,
             std::string& error);
};

}

#endif
