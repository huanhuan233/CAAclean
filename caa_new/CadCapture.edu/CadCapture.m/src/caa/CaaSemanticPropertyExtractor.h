#ifndef CADCAPTURE_CAA_SEMANTIC_PROPERTY_EXTRACTOR_H
#define CADCAPTURE_CAA_SEMANTIC_PROPERTY_EXTRACTOR_H

#include "model/CaptureIdRegistry.h"
#include "model/ReconstructionPackage.h"
#include "caa/CaaNativeBindingIndex.h"
class CATISpecObject;

namespace cadcapture {

// 只在所属文档仍打开时调用；接口探测、单位和单字段失败都封装在实现内。
// 只追加 PropertyFact，不改树节点身份，不保存或更新 CATIA 文档。
class CaaSemanticPropertyExtractor
{
public:
  // 中文：读取本对象的可复用语义属性，引用身份由当前文档的绑定索引解析。
  void Extract(CATISpecObject* spec, const std::string& subject,
               CaptureIdRegistry& ids, ReconstructionPackage& package,
               CaaNativeBindingIndex& bindings);
};
}
#endif
