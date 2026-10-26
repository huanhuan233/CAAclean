/* 声明汇集文档、对象、实例及活动原生接口属性事实的采集入口。 */
#ifndef CADCAPTURE_CAA_CAAPROPERTYEXTRACTORS_H
#define CADCAPTURE_CAA_CAAPROPERTYEXTRACTORS_H

#include "caa/CaaCapabilityBroker.h"
#include "model/ReconstructionPackage.h"
#include "model/CaptureIdRegistry.h"

namespace cadcapture {

/* 属性采用追加方式写入；重复调用不会在此层统一去重。 */
class CaaPropertyExtractors
{
public:
  /* 在指定文档关闭前读取其原生属性；不生成全包的文档和实例展示属性。 */
  bool ExtractNativeFactsForDocument(CaptureIdRegistry& ids,
                                     CaaCapabilityBroker& broker,
                                     ReconstructionPackage& package,
                                     const std::string& document_id);

  /* 汇集全包已有记录及仍有效的原生绑定；返回值不汇总各字段的可读性。 */
  bool Extract(CaptureIdRegistry& ids,
               CaaCapabilityBroker& broker,
               ReconstructionPackage& package);
};

}

#endif
