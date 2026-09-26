#ifndef CADCAPTURE_CAA_COMPOSITE_GEOMETRY_H
#define CADCAPTURE_CAA_COMPOSITE_GEOMETRY_H
#include "model/PropertyFacts.h"
#include <vector>
class CATICciPly;
namespace cadcapture {
// 只读取已存几何；不调用 CreateHighlightShell，不更新源模型。
std::vector<PropertyFact> ReadCompositeGeometry(CATICciPly* ply);
}
#endif
