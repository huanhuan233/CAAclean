// 本文件声明 JSON/JSONL 产物写入器；它只接收纯数据 IR，不接触 CAA 对象。
#ifndef CAD_PARSE_IR_H
#define CAD_PARSE_IR_H

#include "CadParseContracts.h"

namespace cadparse
{
// IArtifactWriter 的轻量 JSON 实现，负责事务式生成全部 JSON/JSONL 产物。
class JsonArtifactWriter : public IArtifactWriter
{
public:
  // 用途：创建写入器，并保存是否启用适合人阅读的 pretty 输出选项。
  // explicit 防止 bool 被意外隐式转换成 JsonArtifactWriter。
  explicit JsonArtifactWriter(bool pretty);

  // 用途：将一次解析的全部纯数据产物写到 output_dir。
  // 返回 false 时 error 给出文件创建、写入或统计校验失败原因。
  bool Write(const std::vector<FeatureRecord>& features,
             const std::vector<RelationRecord>& relations,
             const std::vector<ParameterRecord>& parameters,
             const std::vector<BusinessFeatureRecord>& business_features,
             ParseContext& context,
             const std::string& output_dir,
             std::string& error);

  // 用途：兼容核心自测和简单调用方，自动从 Feature/关系构建派生索引后事务写出。
  bool Write(const std::vector<FeatureRecord>& features,
             const std::vector<RelationRecord>& relations,
             ParseContext& context,
             const std::string& output_dir,
             std::string& error);

private:
  bool _pretty;
};
}

#endif
