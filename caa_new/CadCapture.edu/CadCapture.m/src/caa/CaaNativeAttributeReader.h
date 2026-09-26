#ifndef CADCAPTURE_CAA_NATIVE_ATTRIBUTE_READER_H
#define CADCAPTURE_CAA_NATIVE_ATTRIBUTE_READER_H
#include "model/PropertyFacts.h"
#include <vector>
class CATISpecObject;
namespace cadcapture {
// 与工程语义字段分开存放：保留原生属性名和类型，不猜测单位或按名称覆写语义。
std::vector<PropertyFact> ReadCaaNativeAttributes(CATISpecObject* spec);
}
#endif
