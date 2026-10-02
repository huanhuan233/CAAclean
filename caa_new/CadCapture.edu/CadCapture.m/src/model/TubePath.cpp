#include "model/TubePath.h"
#include <cmath>
#include <limits>
#include <algorithm>
#include <set>
#ifdef min
#undef min
#endif
#ifdef max
#undef max
#endif
namespace cadcapture { namespace {
const double pi=3.14159265358979323846;
// 判断数值是否有限，兼容没有 std::isfinite 的 VS2008。
bool Finite(double v) { return v==v && v<=std::numeric_limits<double>::max() && v>=-std::numeric_limits<double>::max(); }
// 判断三维数据是否全部有效。
bool FinitePoint(const TubeVector& p) { return Finite(p.x)&&Finite(p.y)&&Finite(p.z); }
// 计算向量差，保持毫米单位。
TubeVector Sub(const TubeVector& a,const TubeVector& b) { return TubeVector(a.x-b.x,a.y-b.y,a.z-b.z); }
// 计算向量点积。
double Dot(const TubeVector& a,const TubeVector& b) { return a.x*b.x+a.y*b.y+a.z*b.z; }
// 计算右手系叉积。
TubeVector Cross(const TubeVector& a,const TubeVector& b) { return TubeVector(a.y*b.z-a.z*b.y,a.z*b.x-a.x*b.z,a.x*b.y-a.y*b.x); }
// 计算向量模长。
double Norm(const TubeVector& a) { return std::sqrt(Dot(a,a)); }
// 归一化已验证的非零向量。
TubeVector Unit(const TubeVector& a) { double n=Norm(a); return TubeVector(a.x/n,a.y/n,a.z/n); }
// 对反三角函数输入限制舍入误差。
double Clamp(double v) { return std::max(-1.0,std::min(1.0,v)); }
// 将所有计算结果清空并返回具体失败原因。
TubePathResult Failure(const char* status) { TubePathResult r; r.status=status; return r; }
// 按坐标选择稳定的起点，独立于树节点名称和枚举顺序。
bool Less(const TubeVector& a,const TubeVector& b) { return a.x!=b.x?a.x<b.x:(a.y!=b.y?a.y<b.y:a.z<b.z); }
// 从圆弧三点恢复圆心并验证实测半径、弧长和弧方向。
bool ArcFrame(const TubeSegment& s,double tol,TubeVector& normal,TubeVector& incoming,TubeVector& outgoing,double& angle)
{
  TubeVector a=Sub(s.middle,s.start), b=Sub(s.end,s.start), cross=Cross(a,b);
  double c2=Dot(cross,cross);
  if(c2<=tol*tol*tol*tol) return false;
  TubeVector ca=Cross(b,cross), cb=Cross(cross,a);
  TubeVector offset((Dot(a,a)*ca.x+Dot(b,b)*cb.x)/(2*c2),
                    (Dot(a,a)*ca.y+Dot(b,b)*cb.y)/(2*c2),
                    (Dot(a,a)*ca.z+Dot(b,b)*cb.z)/(2*c2));
  double radius=Norm(offset);
  if(!Finite(radius)||std::fabs(radius-s.radius_mm)>std::max(tol, s.radius_mm*1e-5)) return false;
  normal=Unit(cross);
  TubeVector rs(-offset.x,-offset.y,-offset.z);
  TubeVector re=Sub(b,offset);
  angle=std::atan2(Dot(normal,Cross(rs,re)),Dot(rs,re));
  if(angle<=0) angle+=2*pi;
  if(std::fabs(angle*s.radius_mm-s.length_mm)>std::max(tol,s.length_mm*1e-5)) return false;
  incoming=Unit(Cross(normal,rs)); outgoing=Unit(Cross(normal,re));
  return true;
}
}
// 仅由端点连通性生成几何遍历顺序，所有异常链整体拒绝计算。
TubePathResult AnalyzeTubePath(const std::vector<TubeSegment>& segments,double tolerance)
{
  if(segments.empty()) return Failure("empty_path");
  if(!Finite(tolerance)||tolerance<=0) return Failure("invalid_tolerance");
  const size_t n=segments.size();
  std::vector<TubeVector> ends; std::set<std::string> ids;
  for(size_t i=0;i<n;++i) {
    const TubeSegment& s=segments[i];
    if(s.source_id.empty()||!ids.insert(s.source_id).second) return Failure("duplicate_or_missing_source");
    if(s.kind!="line"&&s.kind!="arc") return Failure("unsupported_curve");
    if(!FinitePoint(s.start)||!FinitePoint(s.middle)||!FinitePoint(s.end)||!Finite(s.length_mm)||!Finite(s.radius_mm)) return Failure("non_finite_geometry");
    if(s.length_mm<=tolerance||Norm(Sub(s.start,s.end))<=tolerance) return Failure("degenerate_or_closed_segment");
    if(s.kind=="arc"&&s.radius_mm<=tolerance) return Failure("invalid_radius");
    ends.push_back(s.start);ends.push_back(s.end);
  }
  std::vector<int> mate(2*n,-1); std::vector<int> terminals;
  for(size_t i=0;i<ends.size();++i) {
    for(size_t j=0;j<ends.size();++j) if(i/2!=j/2&&Norm(Sub(ends[i],ends[j]))<=tolerance) {
      if(mate[i]!=-1) return Failure("branched_or_ambiguous_path"); mate[i]=static_cast<int>(j);
    }
    if(mate[i]==-1) terminals.push_back(static_cast<int>(i));
  }
  if(terminals.size()!=2) return Failure(terminals.empty()?"closed_path":"disconnected_path");
  int cursor=Less(ends[terminals[0]],ends[terminals[1]])?terminals[0]:terminals[1];
  TubePathResult result; std::set<int> visited; TubeVector previous_out, previous_normal;
  bool have_previous=false, have_bend=false; double straight=0;
  while(cursor>=0) {
    int index=cursor/2;
    if(!visited.insert(index).second) return Failure("cyclic_path");
    TubeStep step;step.segment=segments[index];step.reversed=(cursor%2)!=0;
    if(step.reversed) std::swap(step.segment.start,step.segment.end);
    TubeVector in,out,normal;
    if(step.segment.kind=="line") {
      TubeVector d=Sub(step.segment.end,step.segment.start);
      if(std::fabs(Norm(d)-step.segment.length_mm)>std::max(tolerance,step.segment.length_mm*1e-5) ||
         Norm(Sub(step.segment.middle,TubeVector((step.segment.start.x+step.segment.end.x)/2,(step.segment.start.y+step.segment.end.y)/2,(step.segment.start.z+step.segment.end.z)/2)))>tolerance)
        return Failure("inconsistent_line_measurement");
      in=out=Unit(d);straight+=step.segment.length_mm;
    } else {
      double angle=0;
      if(!ArcFrame(step.segment,tolerance,normal,in,out,angle)) return Failure("inconsistent_arc_measurement");
      step.bend_deg=angle*180/pi;step.straight_before_mm=straight;straight=0;
      if(have_bend) {
        step.has_rotation=true;
        step.rotation_deg=std::atan2(Dot(in,Cross(previous_normal,normal)),Clamp(Dot(previous_normal,normal)))*180/pi;
      }
      previous_normal=normal;have_bend=true;
    }
    if(have_previous&&Dot(previous_out,in)<std::cos(0.1*pi/180)) return Failure("non_tangent_path");
    previous_out=out;have_previous=true;
    result.developed_length_mm+=step.segment.length_mm;result.steps.push_back(step);
    cursor=mate[cursor^1];
  }
  if(visited.size()!=n) return Failure("disconnected_path");
  result.trailing_straight_mm=straight;result.status="available";return result;
}
}
