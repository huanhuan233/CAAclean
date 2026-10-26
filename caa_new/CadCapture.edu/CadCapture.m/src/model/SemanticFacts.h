/* 定义特征语义载荷及特征之间的有向依赖记录。 */
#ifndef CADCAPTURE_MODEL_SEMANTICFACTS_H
#define CADCAPTURE_MODEL_SEMANTICFACTS_H

#include <string>

namespace cadcapture {

/* 表达对象的一类语义证据，记录解码层级、来源和可选的已序列化载荷。 */
struct SemanticFacet
{
  std::string facet_id;
  std::string subject_id;
  std::string facet_kind;
  std::string canonical_family;
  std::string decoder_id;
  std::string decode_level;
  std::string decode_status;
  std::string payload_extraction_status;
  /* 保存已编码的 JSON 属性片段，输出层直接拼接，生产者需保证其格式有效。 */
  std::string payload_json_property;
  std::string source_api;
  std::string read_status;

  SemanticFacet() : read_status("unavailable") {}
};

/* 表达特征间有向依赖，具体方向含义由 dependency_kind 约定。 */
struct FeatureDependency
{
  std::string from_feature_id;
  std::string to_feature_id;
  std::string dependency_kind;
  std::string read_status;

  FeatureDependency() : read_status("unavailable") {}
};

}

#endif
