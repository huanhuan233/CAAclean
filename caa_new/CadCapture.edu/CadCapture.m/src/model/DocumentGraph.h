#ifndef CADCAPTURE_MODEL_DOCUMENTGRAPH_H
#define CADCAPTURE_MODEL_DOCUMENTGRAPH_H

#include <string>
#include <vector>

namespace cadcapture {

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

struct DocumentGraph
{
  std::vector<DocumentEntity> documents;
  std::vector<DocumentLink> links;

  void AddDocument(const DocumentEntity& document)
  {
    documents.push_back(document);
  }
};

}

#endif
