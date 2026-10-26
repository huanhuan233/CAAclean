// 定义管路线段、弯曲步骤、合并几何段及路径分析接口。
#ifndef CADCAPTURE_TUBEPATH_H
#define CADCAPTURE_TUBEPATH_H
#include <string>
#include <vector>
namespace cadcapture {
// 用于三维毫米坐标或无量纲方向的简单向量。
struct TubeVector {
  double x, y, z;
  // 初始化毫米坐标或无量纲方向。
  TubeVector(double a=0, double b=0, double c=0):x(a),y(b),z(c) {}
};
// 输入线段或圆弧的三点采样和实测尺寸，由 source_id 追溯来源。
struct TubeSegment {
  std::string source_id;
  std::string kind;
  TubeVector start, middle, end;
  double length_mm, radius_mm;
  // 缺失测量默认无效，由计算入口统一验证。
  TubeSegment():length_mm(0),radius_mm(0) {}
};
// 按路径遍历方向计算的单段工艺量，角度用度、长度与累计里程用毫米。
struct TubeStep {
  TubeSegment segment;
  bool reversed, has_rotation;
  double bend_deg, rotation_deg, straight_before_mm;
  double s0_mm, s1_mm;
  TubeVector tangent_start, tangent_end, bend_center_mm, bend_normal;
  // 首弯没有基准平面，转角必须保持未定义。
  TubeStep():reversed(false),has_rotation(false),bend_deg(0),rotation_deg(0),straight_before_mm(0),s0_mm(0),s1_mm(0) {}
};
// 将连续共线段或同圆同向圆弧合并为几何段，同时保留全部来源 ID。
struct TubeGeometryGroup {
  std::string kind;
  std::vector<std::string> source_ids;
  TubeVector start, end, center, normal;
  double s0_mm, s1_mm, length_mm, radius_mm, bend_deg;
  TubeGeometryGroup():s0_mm(0),s1_mm(0),length_mm(0),radius_mm(0),bend_deg(0) {}
};
// 包含整条管路的排序步骤、合并段和端点；失败结果不保留部分计算输出。
struct TubePathResult {
  std::string status;
  std::vector<TubeStep> steps;
  std::vector<TubeGeometryGroup> groups;
  TubeVector terminal_a, terminal_b;
  bool reverse_direction;
  double developed_length_mm, trailing_straight_mm;
  // 失败时不返回可被误用的半份工艺表。
  TubePathResult():status("unavailable"),reverse_direction(false),developed_length_mm(0),trailing_straight_mm(0) {}
};
// 验证并排序单条开口、相切的直线圆弧链；方向从字典序较小的端点起算。
TubePathResult AnalyzeTubePath(const std::vector<TubeSegment>& segments, double tolerance_mm=0.001, bool reverse_direction=false);
}
#endif
