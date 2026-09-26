#ifndef CADCAPTURE_CAA_PARAMETER_READER_H
#define CADCAPTURE_CAA_PARAMETER_READER_H
#include "model/PropertyFacts.h"
class CATICkeParm;
namespace cadcapture {
// 普通参数和复材参数共用同一读取规则：数值保存 SI，显示字符串保留 CATIA 格式。
PropertyFact ReadCaaParameter(CATICkeParm* parameter);
}
#endif
