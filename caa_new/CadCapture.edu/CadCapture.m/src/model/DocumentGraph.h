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
  std::string capture_status;
  std::string native_document_open_status;

  DocumentEntity()
    : document_kind("unsupported"),
      capture_status("unavailable"),
      native_document_open_status("unavailable")
  {
  }
};

struct DocumentLink
{
  std::string from_document_id;
  std::string to_document_id;
  std::string link_role;
  std::string read_status;

  DocumentLink() : read_status("unavailable") {}
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
