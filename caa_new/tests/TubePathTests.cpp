#include "model/TubePath.h"
#include <cassert>
#include <cmath>
#include <limits>
#include <iostream>
using namespace cadcapture;
// 构造带真实中点与长度的直线样本。
static TubeSegment Line(const char* id,TubeVector a,TubeVector b) {
  TubeSegment s;s.source_id=id;s.kind="line";s.start=a;s.end=b;
  s.middle=TubeVector((a.x+b.x)/2,(a.y+b.y)/2,(a.z+b.z)/2);
  s.length_mm=std::sqrt((a.x-b.x)*(a.x-b.x)+(a.y-b.y)*(a.y-b.y)+(a.z-b.z)*(a.z-b.z));return s;
}
// 构造从正 X 方向转向正 Y 的九十度圆弧。
static TubeSegment Bend() {
  TubeSegment s;s.source_id="bend";s.kind="arc";s.start=TubeVector(10,0,0);s.end=TubeVector(20,10,0);
  s.middle=TubeVector(10+std::sqrt(50.0),10-std::sqrt(50.0),0);s.radius_mm=10;s.length_mm=5*3.14159265358979323846;return s;
}
// 生成两段直线夹一段圆弧的基准链，顺序刻意打乱。
static std::vector<TubeSegment> Sample() {
  std::vector<TubeSegment> s;s.push_back(Line("out",TubeVector(20,10,0),TubeVector(20,20,0)));
  s.push_back(Bend());s.push_back(Line("in",TubeVector(0,0,0),TubeVector(10,0,0)));return s;
}
// 从公共入口验证方向、长度、空间转角及不完整输入拒绝策略。
int main() {
  std::vector<TubeSegment> s=Sample();TubePathResult r=AnalyzeTubePath(s);
  assert(r.status=="available"&&r.steps.size()==3);assert(r.steps[0].segment.source_id=="in");
  assert(std::fabs(r.steps[1].bend_deg-90)<1e-8);assert(!r.steps[1].has_rotation);
  assert(std::fabs(r.developed_length_mm-(20+5*3.14159265358979323846))<1e-8);
  assert(r.steps[1].straight_before_mm==10&&r.trailing_straight_mm==10);
  std::swap(s[1].start,s[1].end);r=AnalyzeTubePath(s);assert(r.status=="available"&&r.steps[1].reversed);
  TubeSegment b;b.source_id="bend2";b.kind="arc";b.start=TubeVector(20,20,0);b.end=TubeVector(20,30,10);
  b.middle=TubeVector(20,20+std::sqrt(50.0),10-std::sqrt(50.0));b.radius_mm=10;b.length_mm=5*3.14159265358979323846;
  s.push_back(b);s.push_back(Line("tail",TubeVector(20,30,10),TubeVector(20,30,20)));r=AnalyzeTubePath(s);
  assert(r.status=="available"&&r.steps[3].has_rotation);assert(std::fabs(r.steps[3].rotation_deg-90)<1e-8);
  s=Sample();s[0].start.y+=1;assert(AnalyzeTubePath(s).status=="disconnected_path");
  s=Sample();s.push_back(Line("branch",TubeVector(10,0,0),TubeVector(10,0,10)));assert(AnalyzeTubePath(s).status=="branched_or_ambiguous_path");
  s=Sample();s.push_back(Line("closing",TubeVector(20,20,0),TubeVector(0,0,0)));assert(AnalyzeTubePath(s).status=="closed_path");
  s=Sample();s[1].radius_mm=11;assert(AnalyzeTubePath(s).status=="inconsistent_arc_measurement");
  s=Sample();s[0]=Line("out",TubeVector(20,10,0),TubeVector(30,10,0));assert(AnalyzeTubePath(s).status=="non_tangent_path");
  s=Sample();s[1].length_mm=std::numeric_limits<double>::quiet_NaN();assert(AnalyzeTubePath(s).status=="non_finite_geometry");
  s=Sample();s[0].source_id=s[1].source_id;assert(AnalyzeTubePath(s).status=="duplicate_or_missing_source");
  s=Sample();s[0].middle.z=1;assert(AnalyzeTubePath(s).status=="inconsistent_line_measurement");
  s=Sample();assert(AnalyzeTubePath(s,0).status=="invalid_tolerance");
  s=Sample();s[1].kind="spline";assert(AnalyzeTubePath(s).status=="unsupported_curve");
  // 大于半圆的弧不能被误算成补角，单弧反向仍应保持实际弧长。
  TubeSegment major;major.source_id="major";major.kind="arc";major.radius_mm=10;
  major.start=TubeVector(0,10,0);major.middle=TubeVector(-std::sqrt(50.0),-std::sqrt(50.0),0);
  major.end=TubeVector(10,0,0);major.length_mm=15*3.14159265358979323846;
  s.clear();s.push_back(major);r=AnalyzeTubePath(s);
  assert(r.status=="available"&&std::fabs(r.steps[0].bend_deg-270)<1e-8);
  s.clear();assert(AnalyzeTubePath(s).status=="empty_path");
  std::cout<<"TubePathTests passed"<<std::endl;return 0;
}
