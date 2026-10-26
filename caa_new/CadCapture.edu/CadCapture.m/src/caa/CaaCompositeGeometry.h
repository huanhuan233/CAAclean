// 声明读取铺层已有轮廓、曲面边界和面积证据的接口。
#ifndef CADCAPTURE_CAA_COMPOSITE_GEOMETRY_H
#define CADCAPTURE_CAA_COMPOSITE_GEOMETRY_H
#include "model/PropertyFacts.h"
#include <vector>
class CATICciPly;
namespace cadcapture {
// 只读取已存几何；不调用 CreateHighlightShell，不更新源模型。
// ply 须非空且仍有效；返回事实尚未分配主体和属性 ID，由调用方统一追加到采集包。
std::vector<PropertyFact> ReadCompositeGeometry(CATICciPly* ply);
}
#endif
