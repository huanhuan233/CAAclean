/* 定义 SDK 能力目录记录与验证阶段查询接口。 */
#ifndef CADCAPTURE_MODEL_SDKCATALOG_H
#define CADCAPTURE_MODEL_SDKCATALOG_H

#include <string>
#include <vector>

namespace cadcapture {

/* 验证阶段按枚举顺序递进，未知阶段不参与通过判定。 */
enum CapabilityVerificationStage
{
  CapabilityStageIndexed,
  CapabilityStageHeaderVerified,
  CapabilityStageCompileVerified,
  CapabilityStageRuntimeVerified,
  CapabilityStageExtractorImplemented,
  CapabilityStageFixtureVerified,
  CapabilityStageReconstructionVerified,
  CapabilityStageUnknown
};

/* 记录 SDK 头文件所属框架与索引路径，默认状态仅表示已索引。 */
struct ApiHeaderRecord
{
  std::string header;
  std::string framework;
  std::string relative_path;
  std::string status;

  ApiHeaderRecord() : status("indexed") {}
};

/* 记录框架根路径及已索引的公开头文件集合。 */
struct FrameworkRecord
{
  std::string framework;
  std::string root;
  std::string status;
  std::vector<std::string> public_headers;

  FrameworkRecord() : status("indexed") {}
};

/* 保存单项能力的验证阶段、实现器和依赖接口，样例及重建验证另有标志。 */
struct CapabilityRecord
{
  std::string capability_id;
  std::string family;
  std::string status;
  std::string extractor;
  bool fixture_verified;
  bool reconstruction_verified;
  std::vector<std::string> headers;
  std::vector<std::string> frameworks;

  CapabilityRecord() : status("indexed"), fixture_verified(false), reconstruction_verified(false) {}
};

/* 持有能力覆盖目录的快照，目录声明不能代替当前模型的采集证据。 */
class SdkCatalog
{
public:
  /* 先清空旧记录再加载指定目录文件；失败时通过 error 返回原因。 */
  bool LoadCapabilityCoverage(const std::string& path, std::string& error);
  /* 返回内部记录的借用指针，未找到返回空；重新加载目录后旧指针失效。 */
  const CapabilityRecord* FindCapability(const std::string& capability_id) const;
  /* 仅比较记录的阶段字符串；找不到能力或阶段未知时返回假。 */
  bool CapabilityAtLeast(const std::string& capability_id, const std::string& required_status) const;
  /* 返回当前已加载的能力记录数量。 */
  size_t CapabilityCount() const;

  /* 识别约定的阶段名称，未知名称返回未知阶段。 */
  static CapabilityVerificationStage StageFromString(const std::string& status);
  /* 双方阶段均已知时才按枚举顺序比较验证程度。 */
  static bool IsStageAtLeast(const std::string& status, const std::string& required_status);

private:
  std::vector<CapabilityRecord> _capabilities;
};

}

#endif
