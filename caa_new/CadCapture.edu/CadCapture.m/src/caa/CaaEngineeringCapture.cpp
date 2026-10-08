#include "caa/CaaEngineeringCapture.h"
#include "caa/CaaGuards.h"
#include "caa/CaaNativeBindingIndex.h"
#include "caa/CaaPropertyEvidence.h"
#include "model/TubePath.h"
#include "output/JsonSupport.h"
#include <CATISpecObject.h>
#include <CATICkeRelationExp.h>
#include <CATICkeParm.h>
#include <CATICkeInst.h>
#include <CATListOfCATBaseUnknown.h>
#include <CATISweep.h>
#include <CATIPrtCenterCurve.h>
#include <CATIPrtProfile.h>
#include <CATIGSMAssemble.h>
#include <CATIGSMLinePtPt.h>
#include <CATIGSMCircle2PointsRad.h>
#include <CATIGSMPlane3Points.h>
#include <CATIMeasurableCurve.h>
#include <CATIMeasurableCircle.h>
#include <CATMathPoint.h>
#include <map>
#include <set>

namespace cadcapture { namespace {
// 获取可选接口，生命周期由 guard 管理，未支持不视为整个模型失败。
template<class T> bool Query(CATBaseUnknown* object,const IID& iid,CaaInterfaceGuard<T>& guard)
{ return object&&SUCCEEDED(object->QueryInterface(iid,reinterpret_cast<void**>(&guard.Out())))&&guard.Get(); }
// 将 CAA 毫米坐标转换为计算模块的值对象。
TubeVector Point(const CATMathPoint& p) { double a[3];p.GetCoord(a);return TubeVector(a[0],a[1],a[2]); }
// 序列化坐标，保留双精度和小数点区域设置。
std::string PointJson(const TubeVector& p)
{ return "["+evidence::Number(p.x)+","+evidence::Number(p.y)+","+evidence::Number(p.z)+"]"; }

// 从已捕获事实投影语义，关联文档关闭后也能与直接打开的零件保持一致。
void ProjectPaths(ReconstructionPackage& package)
{
  std::map<std::string,const PropertyFact*> paths;
  for(size_t i=0;i<package.properties.size();++i) {
    const PropertyFact& fact=package.properties[i];
    if(fact.key=="tube_bending_geometry"&&fact.read_status=="available") paths[fact.subject_id]=&fact;
  }
  for(size_t i=0;i<package.semantic_facets.size();++i) {
    SemanticFacet& facet=package.semantic_facets[i];
    std::map<std::string,const PropertyFact*>::const_iterator found=paths.find(facet.subject_id);
    if(found==paths.end()||facet.payload_json_property.find("\"native_sweep_path\":")!=std::string::npos) continue;
    // 保留原始分类和载荷，几何链证据不足以断言截面是空心导管。
    if(!facet.payload_json_property.empty()) facet.payload_json_property+=",";
    facet.payload_json_property+="\"native_sweep_path\":"+found->second->raw_value;
    facet.payload_extraction_status="available";facet.decode_level="typed";facet.decode_status="success";
    facet.decoder_id="NativeSweepPathDecoder";facet.source_api=found->second->source_api;
  }
}

class Capture {
  CaptureIdRegistry& ids;
  ReconstructionPackage& package;
  CaaNativeBindingIndex bindings;
public:
  // 建立本次采集内的原生对象索引，不依赖名称或跨文件固定编号。
  Capture(CaptureIdRegistry& registry,ReconstructionPackage& target,size_t first_binding)
    :ids(registry),package(target),bindings(target,first_binding) {}
  // 解析引用的真实身份；无法解析时不制造悬空外键。
  std::string Identity(const CATISpecObject_var& object)
  {
    return bindings.Resolve(object);
  }
  // 统一写入带读取状态的属性，供原有 JSONL、数据库和属性面板消费。
  void Put(const std::string& subject,const std::string& key,PropertyFact value,const std::string& group="engineering")
  {
    if(subject.empty()) return;
    evidence::Append(ids,package,subject,group,key,key,value);
    if(value.source_api.find("AnalyzeTubePath")==0) package.properties.back().authority="derived_geometry";
  }
  // 数值明确标记单位及来源，几何派生值不伪装为原生工艺参数。
  void Number(const std::string& subject,const std::string& key,double value,const char* unit,const char* api)
  {
    PropertyFact f=evidence::Text(evidence::Number(value),api);f.value_type="number";f.raw_unit=f.display_unit=unit;
    Put(subject,key,f);
  }
  // 保存引用属性和类型化依赖，保留列表下标，重复名称不会误连。
  std::string Reference(const std::string& subject,const std::string& role,const CATISpecObject_var& object,const char* api)
  {
    const std::string target=Identity(object);
    Put(subject,role,target.empty()?evidence::Failure(object==NULL_var?"unavailable":"not_captured",api):evidence::Text(target,api));
    if(!subject.empty()&&!target.empty()) {
      FeatureDependency d;d.from_feature_id=subject;d.to_feature_id=target;d.dependency_kind=role;d.read_status="available";
      package.feature_dependencies.push_back(d);
    }
    return target;
  }
  // 按原生列表顺序读取公式输入输出；列表属于 CATIA，不释放或改写。
  void Parameters(const std::string& subject,CATCkeListOfParm list,const char* role)
  {
    if(!list) { Put(subject,std::string(role)+"_status",evidence::Failure("unavailable","CATICkeRelation.Parameters"));return; }
    Number(subject,std::string(role)+"_count",list->Size(),"1","CATICkeRelation.Parameters");
    for(int i=1;i<=list->Size();++i) {
      CATISpecObject_var spec((*list)[i]);
      const std::string key=std::string(role)+"_"+evidence::Number(i);
      CATICkeParm_var parameter((*list)[i]);
      if(spec==NULL_var&&parameter!=NULL_var) {
        // 某些计算输入不是规格树对象：保存原生参数自身，不伪造树节点引用。
        Put(subject,key,evidence::Failure("non_spec_parameter","CATICkeRelation.Parameters"));
        try { Put(subject,key+"_name",evidence::Text(evidence::Utf8(parameter->Name()),"CATICkeParm.Name")); }
        catch(...) { Put(subject,key+"_name",evidence::Failure("exception","CATICkeParm.Name")); }
        try { Put(subject,key+"_value_text",evidence::Text(evidence::Utf8(parameter->Show()),"CATICkeParm.Show")); }
        catch(...) { Put(subject,key+"_value_text",evidence::Failure("exception","CATICkeParm.Show")); }
        try {
          CATICkeInst_var value=parameter->Value();
          CATISpecObject_var referenced;
          if(value!=NULL_var) referenced=CATISpecObject_var(value->AsObject());
          Reference(subject,key+"_value_object",referenced,"CATICkeParm.Value.AsObject");
        } catch(...) { Put(subject,key+"_value_object",evidence::Failure("exception","CATICkeParm.Value.AsObject")); }
      } else Reference(subject,key,spec,"CATICkeRelation.Parameters");
    }
  }
  // 仅读取已保存公式，Body(0) 不重新求值或更新模型。
  void Formula(CATISpecObject* spec,const std::string& subject)
  {
    CaaInterfaceGuard<CATICkeRelationExp> relation;
    if(!Query(spec,IID_CATICkeRelationExp,relation)) return;
    try { Put(subject,"formula_expression",evidence::Text(evidence::Utf8(relation.Get()->Body(0)),"CATICkeRelationExp.Body(0)"),"knowledgeware"); }
    catch(...) { Put(subject,"formula_expression",evidence::Failure("exception","CATICkeRelationExp.Body(0)"),"knowledgeware"); }
    try { Parameters(subject,relation.Get()->InParameters(),"formula_input"); }
    catch(...) { Put(subject,"formula_input_status",evidence::Failure("exception","CATICkeRelation.InParameters")); }
    try { Parameters(subject,relation.Get()->OutParameters(),"formula_output"); }
    catch(...) { Put(subject,"formula_output_status",evidence::Failure("exception","CATICkeRelation.OutParameters")); }
    try { Put(subject,"formula_updated",evidence::Text(relation.Get()->IsUpdated()?"true":"false","CATICkeRelation.IsUpdated"),"knowledgeware"); }
    catch(...) { Put(subject,"formula_updated",evidence::Failure("exception","CATICkeRelation.IsUpdated"),"knowledgeware"); }
  }
  // 逐项隔离几何引用读取失败，保留其余成功的控制点和支撑引用。
  template<class T> void ReadReference(T* source,HRESULT(T::*getter)(CATISpecObject_var&),const std::string& subject,const char* role,const char* api)
  {
    try { CATISpecObject_var value;if(SUCCEEDED((source->*getter)(value))) Reference(subject,role,value,api);
      else Put(subject,role,evidence::Failure("failed",api)); }
    catch(...) { Put(subject,role,evidence::Failure("exception",api)); }
  }
  // 读取真实的直线、圆弧、三点平面规格引用，避免从树相邻顺序猜控制点。
  void References(CATISpecObject* spec,const std::string& subject)
  {
    CaaInterfaceGuard<CATIGSMLinePtPt> line;
    if(Query(spec,IID_CATIGSMLinePtPt,line)) {
      ReadReference(line.Get(),&CATIGSMLinePtPt::GetFirstPoint,subject,"line_start_point","CATIGSMLinePtPt.GetFirstPoint");
      ReadReference(line.Get(),&CATIGSMLinePtPt::GetSecondPoint,subject,"line_end_point","CATIGSMLinePtPt.GetSecondPoint");
      ReadReference(line.Get(),&CATIGSMLinePtPt::GetSupport,subject,"line_support","CATIGSMLinePtPt.GetSupport");
    }
    CaaInterfaceGuard<CATIGSMCircle2PointsRad> circle;
    if(Query(spec,IID_CATIGSMCircle2PointsRad,circle)) {
      ReadReference(circle.Get(),&CATIGSMCircle2PointsRad::GetFirstPoint,subject,"arc_first_point","CATIGSMCircle2PointsRad.GetFirstPoint");
      ReadReference(circle.Get(),&CATIGSMCircle2PointsRad::GetSecondPoint,subject,"arc_second_point","CATIGSMCircle2PointsRad.GetSecondPoint");
      ReadReference(circle.Get(),&CATIGSMCircle2PointsRad::GetSupport,subject,"arc_support","CATIGSMCircle2PointsRad.GetSupport");
    }
    CaaInterfaceGuard<CATIGSMPlane3Points> plane;
    if(Query(spec,IID_CATIGSMPlane3Points,plane)) {
      ReadReference(plane.Get(),&CATIGSMPlane3Points::GetFirstPoint,subject,"plane_first_point","CATIGSMPlane3Points.GetFirstPoint");
      ReadReference(plane.Get(),&CATIGSMPlane3Points::GetSecondPoint,subject,"plane_second_point","CATIGSMPlane3Points.GetSecondPoint");
      ReadReference(plane.Get(),&CATIGSMPlane3Points::GetThirdPoint,subject,"plane_third_point","CATIGSMPlane3Points.GetThirdPoint");
    }
  }
  // Export actual 3D line endpoints in the absolute part coordinate system.
  void PreviewLine(CATISpecObject* spec,const std::string& subject)
  {
    CaaInterfaceGuard<CATIGSMLinePtPt> line;
    if(!Query(spec,IID_CATIGSMLinePtPt,line)) return;
    TubeSegment segment;
    if(!Measure(spec,segment)||segment.kind!="line") {
      Put(subject,"native_line_geometry",evidence::Failure("unavailable","CATIMeasurableCurve.GetPoints"));return;
    }
    PropertyFact geometry=evidence::Text("{\"start_mm\":"+PointJson(segment.start)+",\"end_mm\":"+PointJson(segment.end)+",\"coordinate_system\":\"part_absolute\"}","CATIMeasurableCurve.GetPoints");
    geometry.value_type="json";geometry.raw_unit=geometry.display_unit="mm";
    Put(subject,"native_line_geometry",geometry);
  }
  // 读取有限曲线的真实测量，圆弧角由三点及弧长交叉校验；未支持曲线明确拒绝。
  bool Measure(CATISpecObject* spec,TubeSegment& segment)
  {
    CaaInterfaceGuard<CATIMeasurableCurve> curve;
    if(!Query(spec,IID_CATIMeasurableCurve,curve)) return false;
    CATMathPoint a,m,b;
    if(curve.Get()->GetPoints(a,m,b)!=S_OK || curve.Get()->GetLength(segment.length_mm)!=S_OK) return false;
    segment.start=Point(a);segment.middle=Point(m);segment.end=Point(b);
    // R21 对曲线暴露多个测量接口，QI 成功不代表实际形状，必须读取形状枚举。
    CATMeasurableName shape=CATMeasurableUnknown;
    if(curve.Get()->GetShapeName(shape)!=S_OK) return false;
    CaaInterfaceGuard<CATIMeasurableCircle> arc;
    if(shape==CATMeasurableLine) segment.kind="line";
    else if(shape==CATMeasurableCircle&&Query(spec,IID_CATIMeasurableCircle,arc)) {
      segment.kind="arc";if(arc.Get()->GetRadius(segment.radius_mm)!=S_OK) return false;
    } else return false;
    return true;
  }
  // 展开 Join 的真实成员，递归引用遇到环或移除子元素时拒绝不完整的中心线。
  bool Collect(const CATISpecObject_var& spec,std::vector<TubeSegment>& segments,std::set<std::string>& visited)
  {
    const std::string subject=Identity(spec);
    if(subject.empty()||!visited.insert(subject).second) return false;
    CaaInterfaceGuard<CATIPrtCenterCurve> wrapper;
    if(Query(spec,IID_CATIPrtCenterCurve,wrapper)) {
      CATISpecObject_var element;wrapper.Get()->GetElement(element);
      Reference(subject,"centerline_element",element,"CATIPrtCenterCurve.GetElement");
      return element!=NULL_var&&Collect(element,segments,visited);
    }
    CaaInterfaceGuard<CATIGSMAssemble> join;
    if(Query(spec,IID_CATIGSMAssemble,join)) {
      int count=0,removed=0;
      if(join.Get()->GetElementsSize(count)!=S_OK || join.Get()->GetSubElementsSize(removed)!=S_OK || removed || count<=0) return false;
      bool valid=true;
      for(int i=1;i<=count;++i) {
        CATISpecObject_var member;
        if(join.Get()->GetElementAtPosition(member,i)!=S_OK || member==NULL_var) { valid=false;continue; }
        Reference(subject,"join_element_"+evidence::Number(i),member,"CATIGSMAssemble.GetElementAtPosition");
        if(!Collect(member,segments,visited)) valid=false;
      }
      return valid;
    }
    TubeSegment segment;segment.source_id=subject;
    if(!Measure(spec,segment)) {
      Put(subject,"curve_measurement_status",evidence::Failure("unsupported_or_failed","CATIMeasurableCurve"));return false;
    }
    PropertyFact measurement=evidence::Text("{\"start\":"+PointJson(segment.start)+",\"middle\":"+PointJson(segment.middle)+",\"end\":"+PointJson(segment.end)+",\"length\":"+evidence::Number(segment.length_mm)+",\"radius\":"+evidence::Number(segment.radius_mm)+"}","CATIMeasurableCurve.GetPoints/GetLength;CATIMeasurableCircle.GetRadius");
    measurement.value_type="json";measurement.raw_unit=measurement.display_unit="mm";
    Put(subject,"centerline_measurement",measurement);
    segments.push_back(segment);return true;
  }
  // 输出可追溯的几何弯曲表，首弯转角用 null，机床补偿仍标为未提供。
  void Path(const std::string& subject,const std::string& center,const TubePathResult& result)
  {
    const char* api="AnalyzeTubePath(CATIMeasurableCurve;CATIMeasurableCircle)";
    Put(subject,"tube_path_status",evidence::Text(result.status,api),"tube_process");
    if(result.status!="available") return;
    Put(subject,"tube_object_status",evidence::Text("native_sweep_path_candidate;hollow_section_unverified",api),"tube_process");
    std::ostringstream out;out<<"{\"schema_version\":\"tube_geometry_v2\",\"centerline_id\":"<<JsonQuote(center)
      <<",\"direction\":\"lexicographically_smaller_terminal_to_other\",\"reverse_direction\":false,\"terminal_a_mm\":"<<PointJson(result.terminal_a)
      <<",\"terminal_b_mm\":"<<PointJson(result.terminal_b)<<",\"coordinate_system\":\"part_definition\",\"rotation_convention\":\"right_hand_about_incoming_tangent_between_bend_normals\"," 
      <<"\"sequence_kind\":\"geometric_traversal_not_machine_operations\",\"machine_compensation_status\":\"not_provided\","
      <<"\"length_unit\":\"mm\",\"angle_unit\":\"deg\",\"developed_length_mm\":"<<evidence::Number(result.developed_length_mm)
      <<",\"trailing_straight_mm\":"<<evidence::Number(result.trailing_straight_mm)<<",\"segments\":[";
    int bends=0;
    for(size_t i=0;i<result.steps.size();++i) {
      const TubeStep& s=result.steps[i];if(i) out<<",";
      out<<"{\"order\":"<<i+1<<",\"source_id\":"<<JsonQuote(s.segment.source_id)<<",\"kind\":"<<JsonQuote(s.segment.kind)
        <<",\"reversed\":"<<(s.reversed?"true":"false")<<",\"start_mm\":"<<PointJson(s.segment.start)<<",\"middle_mm\":"<<PointJson(s.segment.middle)
        <<",\"end_mm\":"<<PointJson(s.segment.end)<<",\"length_mm\":"<<evidence::Number(s.segment.length_mm)
        <<",\"s0_mm\":"<<evidence::Number(s.s0_mm)<<",\"s1_mm\":"<<evidence::Number(s.s1_mm)
        <<",\"tangent_start\":"<<PointJson(s.tangent_start)<<",\"tangent_end\":"<<PointJson(s.tangent_end);
      if(s.segment.kind=="arc") {
        ++bends;out<<",\"bend_order\":"<<bends<<",\"radius_mm\":"<<evidence::Number(s.segment.radius_mm)<<",\"bend_deg\":"<<evidence::Number(s.bend_deg)
          <<",\"center_mm\":"<<PointJson(s.bend_center_mm)<<",\"plane_normal\":"<<PointJson(s.bend_normal)
          <<",\"straight_before_mm\":"<<evidence::Number(s.straight_before_mm)<<",\"rotation_deg\":"<<(s.has_rotation?evidence::Number(s.rotation_deg):"null");
      }
      out<<"}";
    }
    out<<"],\"geometry_groups\":[";
    for(size_t i=0;i<result.groups.size();++i) {
      const TubeGeometryGroup& group=result.groups[i];if(i) out<<",";
      out<<"{\"order\":"<<i+1<<",\"kind\":"<<JsonQuote(group.kind)<<",\"source_ids\":[";
      for(size_t j=0;j<group.source_ids.size();++j) { if(j) out<<",";out<<JsonQuote(group.source_ids[j]); }
      out<<"],\"start_mm\":"<<PointJson(group.start)<<",\"end_mm\":"<<PointJson(group.end)
         <<",\"s0_mm\":"<<evidence::Number(group.s0_mm)<<",\"s1_mm\":"<<evidence::Number(group.s1_mm)
         <<",\"length_mm\":"<<evidence::Number(group.length_mm);
      if(group.kind=="arc") out<<",\"center_mm\":"<<PointJson(group.center)<<",\"plane_normal\":"<<PointJson(group.normal)
                                <<",\"radius_mm\":"<<evidence::Number(group.radius_mm)<<",\"bend_deg\":"<<evidence::Number(group.bend_deg);
      out<<"}";
    }
    out<<"]}";
    PropertyFact fact=evidence::Text(out.str(),api);fact.value_type="json";
    Put(subject,"tube_bending_geometry",fact,"tube_process");
    int bend_groups=0;
    for(size_t i=0;i<result.groups.size();++i) if(result.groups[i].kind=="arc") ++bend_groups;
    Number(subject,"tube_bend_count",bend_groups,"1",api);
    Number(subject,"tube_developed_length_mm",result.developed_length_mm,"mm",api);
  }
  // 截面是独立证据通道，读取失败不阻止中心线的几何分析。
  void Profile(CATISweep* sweep,const std::string& subject)
  {
    CATISpecObject_var profile_spec=sweep->GetProfile();
    const std::string profile_id=Reference(subject,"sweep_profile",profile_spec,"CATISweep.GetProfile");
    CaaInterfaceGuard<CATIPrtProfile> profile;
    if(Query(profile_spec,IID_CATIPrtProfile,profile)) {
      for(int i=1;i<=profile.Get()->GetElementCount();++i) {
        CATISpecObject_var element;profile.Get()->GetElement(i,element);
        Reference(profile_id,"profile_element_"+evidence::Number(i),element,"CATIPrtProfile.GetElement");
      }
    }
  }
  // 仅沿扫掠特征的真实中心线引用计算，单独隔离截面接口异常。
  void Sweep(CATISpecObject* spec,const std::string& subject)
  {
    CaaInterfaceGuard<CATISweep> sweep;if(!Query(spec,IID_CATISweep,sweep)) return;
    try { Profile(sweep.Get(),subject); }
    catch(...) { Put(subject,"sweep_profile_status",evidence::Failure("exception","CATISweep.GetProfile;CATIPrtProfile")); }
    CATISpecObject_var center=sweep.Get()->GetCenterCurve();
    std::string center_id=Reference(subject,"sweep_centerline",center,"CATISweep.GetCenterCurve");
    std::vector<TubeSegment> segments;std::set<std::string> visited;
    if(center==NULL_var||!Collect(center,segments,visited)) {
      Put(subject,"tube_path_status",evidence::Text("unsupported_or_incomplete_centerline","CaaEngineeringCapture.Collect"),"tube_process");return;
    }
    Path(subject,center_id,AnalyzeTubePath(segments));
  }
};
}
// 为每个对象独立保护公式、引用和扫掠读取，某一接口失败不影响其他零件。
void CaaEngineeringCapture::Extract(CaptureIdRegistry& ids,ReconstructionPackage& package,size_t first_binding)
{
  Capture capture(ids,package,first_binding);
  for(size_t i=first_binding;i<package.native_object_bindings.size();++i) {
    const std::string subject=package.native_object_bindings[i].object_id;
    CATISpecObject* spec=static_cast<CATISpecObject*>(package.native_object_bindings[i].native_spec_object);
    try { capture.Formula(spec,subject); } catch(...) { capture.Put(subject,"formula_capture_status",evidence::Failure("exception","CATICkeRelationExp")); }
    try { capture.References(spec,subject); } catch(...) { capture.Put(subject,"geometry_reference_status",evidence::Failure("exception","CATIGSM")); }
    try { capture.PreviewLine(spec,subject); } catch(...) { capture.Put(subject,"native_line_geometry",evidence::Failure("exception","CATIMeasurableCurve.GetPoints")); }
    try { capture.Sweep(spec,subject); } catch(...) { capture.Put(subject,"tube_path_status",evidence::Failure("exception","CATISweep"),"tube_process"); }
  }
  ProjectPaths(package);
}
}
