/* 定义零件出现模板、投影上下文和 CATPart 枚举接口。 */
#ifndef CADCAPTURE_CAA_CAAPARTENUMERATOR_H
#define CADCAPTURE_CAA_CAAPARTENUMERATOR_H

#include "caa/CaaDocumentHandle.h"
#include "model/CaptureIdRegistry.h"
#include "model/ReconstructionPackage.h"
#include <string>
#include <vector>

namespace cadcapture {

/* 对象定义存放在包中，此处仅保存可被多个装配实例复用的出现模板。 */
struct PartDefinition
{
  std::string document_id;
  std::vector<ObjectOccurrence> occurrence_templates;
};

/* 描述模板在装配中的挂接父节点、路径前缀和所属产品引用。 */
struct ProjectionContext
{
  std::string parent_occurrence_id;
  std::string tree_path_prefix;
  std::string occurrence_path_prefix;
  std::string product_occurrence_id;
  std::string reference_id;
  std::string referenced_document_id;
};

class CaaPartEnumerator
{
public:
  bool Enumerate(CaaDocumentHandle& document_handle,
                 CaptureIdRegistry& ids,
                 ReconstructionPackage& package,
                 std::string& error);

  /* 采集定义及父节点在前的出现模板；原生绑定仅在对应文档仍打开时可用。 */
  bool CaptureDefinition(CaaDocumentHandle& document_handle,
                         CaptureIdRegistry& ids,
                         PartDefinition& definition,
                         ReconstructionPackage& package,
                         std::string& error,
                         bool register_native_objects);

  /* 复用已有对象 ID，为每个模板分配新的出现 ID 并重建父子关系。 */
  bool ProjectDefinition(const PartDefinition& definition,
                         const ProjectionContext& context,
                         CaptureIdRegistry& ids,
                         ReconstructionPackage& package,
                         std::string& error);
};

}

#endif
