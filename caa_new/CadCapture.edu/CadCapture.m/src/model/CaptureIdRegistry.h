/* 声明单次采集内各类实体独立递增的标识分配器。 */
#ifndef CADCAPTURE_MODEL_CAPTUREIDREGISTRY_H
#define CADCAPTURE_MODEL_CAPTUREIDREGISTRY_H

#include <string>

namespace cadcapture {

/* 每类实体单独计数；生成值只保证同一个分配器内唯一，不代表跨会话稳定身份。 */
class CaptureIdRegistry
{
public:
  /* 各类别计数从 1 开始，新建分配器会重新分配同样的序列。 */
  CaptureIdRegistry();

  /* 分配新的文档标识，用于包内记录引用。 */
  std::string NextDocumentId();
  /* 分配新的对象定义标识，用于包内记录引用。 */
  std::string NextObjectId();
  /* 分配新的对象树位置标识，用于包内记录引用。 */
  std::string NextOccurrenceId();
  /* 分配新的产品引用标识，用于包内记录引用。 */
  std::string NextProductReferenceId();
  /* 分配新的产品实例标识，用于包内记录引用。 */
  std::string NextProductOccurrenceId();
  /* 分配新的文档链接标识，用于包内记录引用。 */
  std::string NextDocumentLinkId();
  /* 分配新的属性事实标识，用于包内记录引用。 */
  std::string NextPropertyFactId();
  /* 分配新的语义切面标识，用于包内记录引用。 */
  std::string NextSemanticFacetId();
  /* 分配新的几何表示标识，用于包内记录引用。 */
  std::string NextGeometryId();
  /* 分配新的拓扑实体标识，用于包内记录引用。 */
  std::string NextTopologyId();
  /* 分配新的PMI 实体标识，用于包内记录引用。 */
  std::string NextPmiId();
  /* 分配新的诊断标识，用于包内记录引用。 */
  std::string NextDiagnosticId();

private:
  /* 拼接前缀与当前序号后递增对应计数器。 */
  std::string Next(const char* prefix, long& value);

  long _document_index;
  long _object_index;
  long _occurrence_index;
  long _product_reference_index;
  long _product_occurrence_index;
  long _document_link_index;
  long _property_fact_index;
  long _semantic_facet_index;
  long _geometry_index;
  long _topology_index;
  long _pmi_index;
  long _diagnostic_index;
};

}

#endif
