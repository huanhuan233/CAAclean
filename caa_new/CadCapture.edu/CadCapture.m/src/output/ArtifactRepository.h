/* 声明经暂存核验和目录替换发布采集产物的仓储接口。 */
#ifndef CADCAPTURE_OUTPUT_ARTIFACTREPOSITORY_H
#define CADCAPTURE_OUTPUT_ARTIFACTREPOSITORY_H

#include "engine/CaptureReport.h"
#include "model/ReconstructionPackage.h"
#include <string>

namespace cadcapture {

/* 统一负责目录所有权校验、暂存写出、核验和发布，调用方无需直接管理备份。 */
class ArtifactRepository
{
public:
  /* 完整产物核验后才替换目标目录；返回成功后仍可能在 error 中保留清理警告。 */
  bool Commit(const ReconstructionPackage& package,
              const CaptureReport& report,
              const std::string& output_dir,
              bool pretty,
              std::string& error);
};

}

#endif
