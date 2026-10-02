#ifndef CADCAPTURE_TUBEPATH_H
#define CADCAPTURE_TUBEPATH_H
#include <string>
#include <vector>
namespace cadcapture {
struct TubeVector {
  double x, y, z;
  // 初始化毫米坐标或无量纲方向。
  TubeVector(double a=0, double b=0, double c=0):x(a),y(b),z(c) {}
};
struct TubeSegment {
  std::string source_id;
  std::string kind;
  TubeVector start, middle, end;
  double length_mm, radius_mm;
  // 缺失测量默认无效，由计算入口统一验证。
  TubeSegment():length_mm(0),radius_mm(0) {}
};
struct TubeStep {
  TubeSegment segment;
  bool reversed, has_rotation;
  double bend_deg, rotation_deg, straight_before_mm;
  // 首弯没有基准平面，转角必须保持未定义。
  TubeStep():reversed(false),has_rotation(false),bend_deg(0),rotation_deg(0),straight_before_mm(0) {}
};
struct TubePathResult {
  std::string status;
  std::vector<TubeStep> steps;
  double developed_length_mm, trailing_straight_mm;
  // 失败时不返回可被误用的半份工艺表。
  TubePathResult():status("unavailable"),developed_length_mm(0),trailing_straight_mm(0) {}
};
// 验证并排序单条开口、相切的直线圆弧链；方向从字典序较小的端点起算。
TubePathResult AnalyzeTubePath(const std::vector<TubeSegment>& segments, double tolerance_mm=0.001);
}
#endif
