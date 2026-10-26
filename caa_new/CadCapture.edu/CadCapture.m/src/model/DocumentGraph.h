/* 定义被采集文档及文档间引用链接的数据模型。 */
#ifndef CADCAPTURE_MODEL_DOCUMENTGRAPH_H
#define CADCAPTURE_MODEL_DOCUMENTGRAPH_H

#include <string>
#include <vector>

namespace cadcapture {

/* 文档节点分别记录打开、加载和定义采集状态，不能仅凭节点存在判定可用。 */
struct DocumentEntity
{
  std::string document_id;
  std::string document_kind;
  std::string source_file_name;
  std::string display_name;
  std::string load_status;
  std::string capture_status;
  std::string native_document_open_status;
  std::string definition_status;
  std::string identity_method;

  DocumentEntity()
    : document_kind("unsupported"),
      load_status("unavailable"),
      capture_status("unavailable"),
      native_document_open_status("unavailable"),
      definition_status("unavailable"),
      identity_method("unavailable")
  {
  }
};

/* 以文档 ID 连接来源和目标，并保留对应产品引用及读取证据。 */
struct DocumentLink
{
  std::string link_id;
  std::string from_document_id;
  std::string to_document_id;
  std::string reference_id;
  std::string link_role;
  std::string link_status;
  std::string value_source;
  std::string read_status;

  DocumentLink() : link_status("unavailable"), value_source("unavailable"), read_status("unavailable") {}
};

/* 保存本次采集的文档节点和跨文档链接，不负责打开或关闭原生文档。 */
struct DocumentGraph
{
  std::vector<DocumentEntity> documents;
  std::vector<DocumentLink> links;

  /* 追加一个文档节点；调用方负责去重和分配文档 ID。 */
  void AddDocument(const DocumentEntity& document)
  {
    documents.push_back(document);
  }
};

}

#endif
