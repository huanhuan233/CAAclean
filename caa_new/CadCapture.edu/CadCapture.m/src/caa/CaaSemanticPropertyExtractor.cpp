#include "caa/CaaSemanticPropertyExtractor.h"
#include "caa/CaaParameterReader.h"
#include "caa/CaaCompositeGeometry.h"
#include "caa/CaaNativeAttributeReader.h"
#include "caa/CaaPropertyEvidence.h"
#include "caa/CaaGuards.h"
#include <CATISpecObject.h>
#include <CATIAllowUserInfo.h>
#include <CATICkeParm.h>
#include <CATICciMaterialCache.h>
#include <CATICciPhysicalEntity.h>
#include <CATICciPly.h>
#include <CATICciPliesGroup.h>
#include <CATICciStacking.h>
#include <CATICciCompositesParameters.h>
#include <CATIACompositesMaterial.h>
#include <CATIMaterialFeature.h>
#include <CATIMf3DAxisSystem.h>
#include <CATMathAxis.h>
#include <CATMathPoint.h>
#include <CATMathVector.h>

namespace cadcapture {
namespace {

// 内部适配器使用强类型接口，不用树节点名称猜测零件类型；普通零件可不支持复材。
template<class T> bool Acquire(CATBaseUnknown* object, const IID& iid, CaaInterfaceGuard<T>& guard)
{
  return object && SUCCEEDED(object->QueryInterface(iid, reinterpret_cast<void**>(&guard.Out()))) && guard.Get();
}

class Capture
{
public:
  // 中文：同一文档的属性通道共享已构建的原生对象索引。
  Capture(const std::string& subject, CaptureIdRegistry& ids, ReconstructionPackage& package,
          CaaNativeBindingIndex& bindings)
    : _subject(subject), _ids(ids), _package(package), _bindings(bindings) {}

  void Put(const std::string& key, PropertyFact fact, const std::string& group = "composites")
  {
    evidence::Append(_ids, _package, _subject, group, key, key, fact);
  }

  void Reference(const std::string& key, const CATISpecObject_var& reference, const std::string& api)
  {
    if (reference == NULL_var) { Put(key, evidence::Failure("unavailable", api)); return; }
    Put(key, evidence::Text(evidence::Utf8(reference->GetDisplayName()), api));
    // 名称允许重复，另存已发现对象的 ID；未发现时明确记录，不凭名称建立关系。
    const std::string object_id = _bindings.Resolve(reference);
    Put(key + "_object_id", object_id.empty() ? evidence::Failure("not_captured", api) : evidence::Text(object_id, api));
  }

  template<class T> void Parameter(T* source, HRESULT (T::*getter)(CATICkeParm_var&),
                                    const char* key, const char* api)
  {
    PropertyFact fact = evidence::Failure("failed", api);
    try
    {
      CATICkeParm_var parameter;
      if (SUCCEEDED((source->*getter)(parameter))) fact = ReadCaaParameter(parameter);
      fact.source_api = std::string(api) + " -> " + fact.source_api;
    }
    catch (...) { fact = evidence::Failure("exception", api); }
    Put(key, fact);
  }

  template<class T> void String(T* source, HRESULT (T::*getter)(CATUnicodeString&),
                                 const char* key, const char* api)
  {
    PropertyFact fact = evidence::Failure("failed", api);
    try
    {
      CATUnicodeString value;
      if (SUCCEEDED((source->*getter)(value))) fact = evidence::Text(evidence::Utf8(value), api);
    }
    catch (...) { fact = evidence::Failure("exception", api); }
    Put(key, fact);
  }

  void Axis(const CATMathAxis& axis, const std::string& prefix, const std::string& api)
  {
    CATMathPoint origin;
    CATMathVector vectors[3];
    axis.GetOrigin(origin);
    axis.GetFirstDirection(vectors[0]); axis.GetSecondDirection(vectors[1]); axis.GetThirdDirection(vectors[2]);
    const char* labels[] = {"x", "y", "z"};
    double xyz[3];
    origin.GetCoord(xyz);
    for (int n = 0; n < 3; ++n) Numeric(prefix + "_origin_" + labels[n], xyz[n], "mm", api);
    for (int i = 0; i < 3; ++i)
    {
      vectors[i].GetCoord(xyz);
      for (int j = 0; j < 3; ++j) Numeric(prefix + "_" + labels[i] + "_" + labels[j], xyz[j], "1", api);
    }
  }

  void Numeric(const std::string& key, double value, const std::string& unit, const std::string& api)
  {
    PropertyFact fact = evidence::Text(evidence::Number(value), api);
    fact.value_type = "number";
    fact.raw_unit = fact.display_unit = unit;
    Put(key, fact);
  }

  void Material(CATICciMaterialCache* material)
  {
    String(material, &CATICciMaterialCache::GetName, "composite_material_name", "CATICciMaterialCache.GetName");
    String(material, &CATICciMaterialCache::GetType, "composite_material_type", "CATICciMaterialCache.GetType");
    Parameter(material, &CATICciMaterialCache::GetMaterialCuredThickness, "composite_cured_thickness", "CATICciMaterialCache.GetMaterialCuredThickness");
    Parameter(material, &CATICciMaterialCache::GetMaterialUncuredThickness, "composite_uncured_thickness", "CATICciMaterialCache.GetMaterialUncuredThickness");
    Parameter(material, &CATICciMaterialCache::GetMaterialRollWidth, "composite_roll_width", "CATICciMaterialCache.GetMaterialRollWidth");
    Parameter(material, &CATICciMaterialCache::GetMaterialMaxDefmn, "composite_warning_angle", "CATICciMaterialCache.GetMaterialMaxDefmn");
    Parameter(material, &CATICciMaterialCache::GetMaterialLimDefmn, "composite_limit_angle", "CATICciMaterialCache.GetMaterialLimDefmn");
    Parameter(material, &CATICciMaterialCache::GetMaterialSurMass, "composite_surfacic_weight", "CATICciMaterialCache.GetMaterialSurMass");
    Parameter(material, &CATICciMaterialCache::GetMaterialCompDensity, "composite_density", "CATICciMaterialCache.GetMaterialCompDensity");
    // 价格在关联的材料对象上，不拿惯性密度或 XML 的固定数字替代读取结果。
    const char* api = "CATIACompositesMaterial.get_MassCost";
    PropertyFact cost = evidence::Failure("unavailable", api);
    try
    {
      CATIMaterialFeature_var feature;
      if (SUCCEEDED(material->GetMaterial(feature)) && feature != NULL_var)
      {
        CaaInterfaceGuard<CATIACompositesMaterial> composite;
        if (Acquire(feature, IID_CATIACompositesMaterial, composite))
        {
          double value = 0;
          if (SUCCEEDED(composite.Get()->get_MassCost(value)))
          {
            cost = evidence::Text(evidence::Number(value), api);
            cost.value_type = "number";
            cost.raw_unit = cost.display_unit = "USD/kg";
          }
          else cost.read_status = "failed";
        }
        else cost.read_status = "unsupported";
      }
    }
    catch (...) { cost.read_status = "exception"; }
    Put("composite_cost_per_mass", cost);
  }

  void Physical(CATICciPhysicalEntity* physical)
  {
    Parameter(physical, &CATICciPhysicalEntity::GetDirection, "composite_orientation", "CATICciPhysicalEntity.GetDirection");
    try
    {
      CATICciMaterialCache_var material;
      if (SUCCEEDED(physical->GetMaterialCache(material)) && material != NULL_var) Material(material);
      else Put("composite_material_status", evidence::Failure("unavailable", "CATICciPhysicalEntity.GetMaterialCache"));
    }
    catch (...) { Put("composite_material_status", evidence::Failure("exception", "CATICciPhysicalEntity.GetMaterialCache")); }
    try
    {
      CATIMf3DAxisSystem_var rosette;
      if (SUCCEEDED(physical->GetRosette(rosette)) && rosette != NULL_var)
      {
        CATISpecObject_var spec(rosette);
        Reference("composite_rosette", spec, "CATICciPhysicalEntity.GetRosette");
        CATMathAxis axis;
        if (SUCCEEDED(rosette->GetMathAxis(axis))) Axis(axis, "composite_rosette", "CATIMf3DAxisSystem.GetMathAxis");
        else Put("composite_rosette_axis", evidence::Failure("failed", "CATIMf3DAxisSystem.GetMathAxis"));
      }
      else Put("composite_rosette", evidence::Failure("unavailable", "CATICciPhysicalEntity.GetRosette"));
    }
    catch (...) { Put("composite_rosette", evidence::Failure("exception", "CATICciPhysicalEntity.GetRosette")); }
  }

  template<class T> void Shell(T* object, const char* api)
  {
    try
    {
      CATISpecObject_var shell;
      CATBoolean direction = FALSE;
      if (SUCCEEDED(object->GetReferenceShell(shell, direction)))
      {
        Reference("composite_reference_surface", shell, api);
        Put("composite_draping_direction", evidence::Text(direction ? "POSITIVE" : "NEGATIVE", api));
      }
      else Put("composite_reference_surface", evidence::Failure("failed", api));
    }
    catch (...) { Put("composite_reference_surface", evidence::Failure("exception", api)); }
  }

  void Knowledge(CATICkeParm* parameter)
  {
    PropertyFact value = ReadCaaParameter(parameter);
    std::string name = value.display_name;
    const std::string::size_type pos = name.find_last_of("/\\");
    if (pos != std::string::npos) name = name.substr(pos + 1);
    // 保留旧键名，让已有树标签和入库读取器继续工作；原始全名另存。
    Put("catia_parameter_qualified_name", value.display_name.empty() ? evidence::Failure("unavailable", "CATICkeParm.Name")
                                                                   : evidence::Text(value.display_name, "CATICkeParm.Name"), "knowledgeware");
    PropertyFact name_fact = name.empty() ? evidence::Failure("unavailable", "CATICkeParm.Name") : evidence::Text(name, "CATICkeParm.Name");
    name_fact.raw_display_text = value.raw_display_text;
    name_fact.read_only = value.read_only; name_fact.hidden_status = value.hidden_status;
    Put("catia_parameter_name", name_fact, "knowledgeware");
    Put("catia_parameter_kind", value.value_type == "unknown" ? evidence::Failure("unavailable", "CATICkeParm.Type")
                                                             : evidence::Text(value.value_type, "CATICkeParm.Type"), "knowledgeware");
    Put(value.read_status == "available" ? "catia_parameter_value_text" : "catia_parameter_value_status", value, "knowledgeware");
  }

  void Palette(CATICciCompositesParameters* parameters)
  {
    int count = 0;
    if (FAILED(parameters->GetNumberOfDirections(count)))
    {
      Put("composite_direction_count", evidence::Failure("failed", "CATICciCompositesParameters.GetNumberOfDirections"));
      return;
    }
    Numeric("composite_direction_count", count, "1", "CATICciCompositesParameters.GetNumberOfDirections");
    for (int i = 1; i <= count; ++i)
    {
      const std::string key = "composite_direction_" + evidence::Number(i);
      try
      {
        CATICkeParm_var direction;
        int red = 0, green = 0, blue = 0;
        if (SUCCEEDED(parameters->GetDirection(i, direction, red, green, blue)))
        {
          PropertyFact fact = ReadCaaParameter(direction);
          fact.source_api = "CATICciCompositesParameters.GetDirection -> " + fact.source_api;
          Put(key, fact);
          Put(key + "_rgb", evidence::Text(evidence::Number(red) + "," + evidence::Number(green) + "," + evidence::Number(blue),
                                           "CATICciCompositesParameters.GetDirection"));
        }
        else Put(key, evidence::Failure("failed", "CATICciCompositesParameters.GetDirection"));
      }
      catch (...) { Put(key, evidence::Failure("exception", "CATICciCompositesParameters.GetDirection")); }
    }
  }

private:
  std::string _subject;
  CaptureIdRegistry& _ids;
  ReconstructionPackage& _package;
  CaaNativeBindingIndex& _bindings;
};
}

// 中文：每个接口通道独立容错，属性事实只追加到本次采集包。
void CaaSemanticPropertyExtractor::Extract(CATISpecObject* spec, const std::string& subject,
                                           CaptureIdRegistry& ids, ReconstructionPackage& package,
                                           CaaNativeBindingIndex& bindings)
{
  if (!spec) return;
  Capture capture(subject, ids, package, bindings);
  // 每条通道独立保护；一个旧模型接口抛异常，不影响其余属性、后续零件的采集。
  try { CaaInterfaceGuard<CATICkeParm> value; if (Acquire(spec, IID_CATICkeParm, value)) capture.Knowledge(value.Get()); }
  catch (...) { capture.Put("catia_parameter_value_status", evidence::Failure("exception", "CATICkeParm"), "knowledgeware"); }
  try
  {
    CaaInterfaceGuard<CATIAllowUserInfo> info;
    if (Acquire(spec, IID_CATIAllowUserInfo, info))
      capture.Put("catia_user_comment", evidence::Text(evidence::Utf8(info.Get()->GetComment()), "CATIAllowUserInfo.GetComment"), "knowledgeware");
  }
  catch (...) { capture.Put("catia_user_comment", evidence::Failure("exception", "CATIAllowUserInfo.GetComment"), "knowledgeware"); }
  bool is_physical = false;
  bool is_composite = false;
  try
  {
    CaaInterfaceGuard<CATICciPhysicalEntity> physical;
    is_physical = Acquire(spec, IID_CATICciPhysicalEntity, physical);
    is_composite = is_physical;
    if (is_physical) capture.Physical(physical.Get());
  }
  catch (...) { capture.Put("composite_physical_status", evidence::Failure("exception", "CATICciPhysicalEntity")); }
  // 铺层的材料必须沿 GetMaterialCache 读取；不要把铺层自己当材料缓存再读一次。
  if (!is_physical)
  {
    try { CaaInterfaceGuard<CATICciMaterialCache> material; if (Acquire(spec, IID_CATICciMaterialCache, material)) { is_composite = true; capture.Material(material.Get()); } }
    catch (...) { capture.Put("composite_material_status", evidence::Failure("exception", "CATICciMaterialCache")); }
  }
  try { CaaInterfaceGuard<CATICciCompositesParameters> parameters; if (Acquire(spec, IID_CATICciCompositesParameters, parameters)) { is_composite = true; capture.Palette(parameters.Get()); } }
  catch (...) { capture.Put("composite_parameters_status", evidence::Failure("exception", "CATICciCompositesParameters")); }
  try
  {
    CaaInterfaceGuard<CATICciPly> ply;
    if (Acquire(spec, IID_CATICciPly, ply))
    {
      capture.Shell(ply.Get(), "CATICciPly.GetReferenceShell");
      const std::vector<PropertyFact> geometry = ReadCompositeGeometry(ply.Get());
      for (size_t i = 0; i < geometry.size(); ++i) capture.Put(geometry[i].key, geometry[i]);
    }
  }
  catch (...) { capture.Put("composite_ply_status", evidence::Failure("exception", "CATICciPly")); }
  try
  {
    CaaInterfaceGuard<CATICciPliesGroup> group;
    if (Acquire(spec, IID_CATICciPliesGroup, group))
    {
      is_composite = true;
      capture.Shell(group.Get(), "CATICciPliesGroup.GetReferenceShell");
      CATMathAxis axis;
      if (SUCCEEDED(group.Get()->GetRosette(axis))) capture.Axis(axis, "composite_rosette", "CATICciPliesGroup.GetRosette");
      else capture.Put("composite_rosette", evidence::Failure("failed", "CATICciPliesGroup.GetRosette"));
    }
  }
  catch (...) { capture.Put("composite_group_status", evidence::Failure("exception", "CATICciPliesGroup")); }
  try
  {
    CaaInterfaceGuard<CATIMf3DAxisSystem> axis;
    if (Acquire(spec, IID_CATIMf3DAxisSystem, axis))
    {
      CATMathAxis math;
      if (SUCCEEDED(axis.Get()->GetMathAxis(math))) capture.Axis(math, "axis", "CATIMf3DAxisSystem.GetMathAxis");
      else capture.Put("axis_status", evidence::Failure("failed", "CATIMf3DAxisSystem.GetMathAxis"));
    }
  }
  catch (...) { capture.Put("axis_status", evidence::Failure("exception", "CATIMf3DAxisSystem")); }
  try
  {
    CaaInterfaceGuard<CATICciStacking> stacking;
    if (Acquire(spec, IID_CATICciStacking, stacking)) is_composite = true;
    if (is_composite)
    {
      const std::vector<PropertyFact> attributes = ReadCaaNativeAttributes(spec);
      for (size_t i = 0; i < attributes.size(); ++i) capture.Put(attributes[i].key, attributes[i], "native_attributes");
    }
  }
  catch (...) { capture.Put("native_attribute_scan_status", evidence::Failure("exception", "CATISpecAttrAccess"), "native_attributes"); }
}
}
