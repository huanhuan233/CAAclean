/* 定义对象实体、原生身份及身份稳定范围的数据模型。 */
#ifndef CADCAPTURE_MODEL_OBJECTIDENTITY_H
#define CADCAPTURE_MODEL_OBJECTIDENTITY_H

#include <string>

namespace cadcapture {

/* 声明身份有效范围，文档局部和会话局部都不自动承诺全局稳定。 */
enum IdentityStabilityScope
{
  IdentityDocumentLocal,
  IdentitySessionLocal,
  IdentityUnavailable
};

/* 同时保留包内 ID 与原生身份读取结果；稳定性由 scope 和读取状态限定。 */
struct ObjectIdentity
{
  std::string capture_id;
  std::string native_identity;
  std::string identity_method;
  std::string stable_id;
  std::string native_label;
  IdentityStabilityScope scope;
  std::string read_status;

  ObjectIdentity() : scope(IdentityUnavailable), read_status("unavailable") {}
};

/* 表示原生对象的定义与属性身份；同一对象可对应多个树位置记录。 */
struct ObjectEntity
{
  std::string object_id;
  std::string document_id;
  std::string object_kind;
  std::string display_name;
  std::string internal_name;
  std::string startup_type;
  std::string update_status;
  std::string supplemental_sources;
  ObjectIdentity identity;
  std::string capture_status;

  ObjectEntity() : capture_status("unavailable") {}
};

}

#endif
