/* 声明读取 FTA 组件类型化字段并保留单位及读取状态的接口。 */
#ifndef CADCAPTURE_CAA_CAAFTATYPEDREADER_H
#define CADCAPTURE_CAA_CAAFTATYPEDREADER_H

#include "model/PmiIR.h"

class CATITPSComponent;

namespace cadcapture {

// Reads only values exposed by the installed R21 interfaces. Unknown semantics
// remain raw fields with explicit status; this function never changes a model.
/* component 为借用接口；仅追加字段与接口证据，几何引用尚未映射时维持未验证状态。 */
void ReadFtaTypedFields(CATITPSComponent* component, FtaSemanticEntity& entity);

}

#endif
