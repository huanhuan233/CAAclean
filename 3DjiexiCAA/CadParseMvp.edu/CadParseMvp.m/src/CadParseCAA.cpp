// 本文件是解析器与 CATIA V5R21 PublicInterfaces 的边界。
// 它负责引用计数、Session/Document 生命周期、类型指纹采集和确定性规格树遍历。
#include "CadParseCAA.h"

#include "CATBaseUnknown.h"
#include "CATDocument.h"
#include "CATDocumentServices.h"
#include "CATIContainer.h"
#include "CATInit.h"
#include "CATIPrtContainer.h"
#include "CATIPrtPart.h"
#include "CATISpecObject.h"
#include "CATLISTV_CATISpecObject.h"
#include "CATICkeInst.h"
#include "CATICkeParm.h"
#include "CATICkeType.h"
#include "CATSession.h"
#include "CATSessionServices.h"
#include "CATUnicodeString.h"
#include "CATIAHole.h"
#include "CATIALimit.h"
#include "CATIALength.h"
#include "CATIAAngle.h"
#include "CATIAStrParam.h"
#include "CATHoleDefs.h"
#include "CATLimitDefs.h"
#include "CATSafeArray.h"

#include <algorithm>
#include <cstring>
#include <sstream>
#include <sys/stat.h>
#include <vector>

namespace cadparse
{
// 通用 CAA 接口指针 RAII 守卫。
// 模板参数 T 保留具体接口类型；守卫接管一个已持有引用，并在析构时调用一次 Release。
template <class T>
class CaaInterfaceGuard
{
public:
  // 用途：接管 pointer 当前代表的 CAA 引用；允许传入空指针。
  explicit CaaInterfaceGuard(T* pointer = 0) : _pointer(pointer) {}
  // 用途：释放构造时接管的引用；不释放空指针。
  ~CaaInterfaceGuard() { if (_pointer) _pointer->Release(); }
  // 用途：返回借用指针供当前作用域调用；调用者不能额外 Release。
  T* Get() const { return _pointer; }
  // 用途：把受保护的输出槽交给 QueryInterface/getter；即使调用抛异常也能释放已写入引用。
  T*& Out() { return _pointer; }

private:
  // 用途：禁止复制守卫，避免两个析构函数对同一引用重复 Release。
  CaaInterfaceGuard(const CaaInterfaceGuard&);
  // 用途：禁止赋值，保持引用清理责任唯一。
  CaaInterfaceGuard& operator=(const CaaInterfaceGuard&);
  T* _pointer;
};

// CATBSTR 专用 RAII；R21 CATBSTR.h 要求由 CATFreeString 而不是 SysFreeString 释放。
class CaaBstrGuard
{
public:
  // 用途：创建空字符串输出槽，供 Automation getter 写入。
  CaaBstrGuard() : _value(0) {}
  // 用途：按照 CATBSTR Public 契约释放已返回字符串。
  ~CaaBstrGuard() { if (_value) CATFreeString(_value); }
  // 用途：返回 getter 所需的引用输出槽。
  CATBSTR& Out() { return _value; }
  // 用途：借用已返回字符串进行 UTF-8 转换。
  CATBSTR Get() const { return _value; }
private:
  CaaBstrGuard(const CaaBstrGuard&);
  CaaBstrGuard& operator=(const CaaBstrGuard&);
  CATBSTR _value;
};

// ListComponents 返回的堆分配列表专用守卫；该列表按 R21 API 契约使用 delete 销毁。
class SpecListGuard
{
public:
  // 用途：接管 CATISpecObject 列表对象的所有权。
  explicit SpecListGuard(CATListValCATISpecObject_var* list) : _list(list) {}
  // 用途：释放整个列表包装对象；列表内的 _var 元素自行管理各自引用。
  ~SpecListGuard() { delete _list; }

private:
  // 用途：禁止复制列表所有者，避免重复 delete。
  SpecListGuard(const SpecListGuard&);
  // 用途：禁止列表守卫赋值，保持唯一所有权。
  SpecListGuard& operator=(const SpecListGuard&);
  CATListValCATISpecObject_var* _list;
};

// CATIContainer::ListMembersHere 输出序列的引用清理守卫。
// 序列本身由调用栈保存，但其中每个 CATBaseUnknown_ptr 都需要显式 Release。
class BaseUnknownSequenceGuard
{
public:
  // 用途：借用序列对象，并承担其所有非空成员引用的清理责任。
  explicit BaseUnknownSequenceGuard(SEQUENCE(CATBaseUnknown_ptr)& sequence)
    : _sequence(sequence) {}
  // 用途：遍历序列、逐个 Release，并置零以避免悬空指针被再次使用。
  ~BaseUnknownSequenceGuard()
  {
    CATLONG32 index = 0;
    for (index = 0; index < _sequence.length(); ++index)
    {
      if (_sequence[index])
      {
        _sequence[index]->Release();
        _sequence[index] = 0;
      }
    }
  }

private:
  // 用途：禁止复制清理守卫，避免同一序列成员被释放两次。
  BaseUnknownSequenceGuard(const BaseUnknownSequenceGuard&);
  // 用途：禁止赋值；引用成员本身也不适合重新绑定。
  BaseUnknownSequenceGuard& operator=(const BaseUnknownSequenceGuard&);
  SEQUENCE(CATBaseUnknown_ptr)& _sequence;
};

// 用途：通过 R21 ConvertToUTF8 API 把 CATUnicodeString 复制为独立 std::string。
// 每个 Unicode 字符最多预留四个 UTF-8 字节，并额外保留终止零字节空间。
std::string UnicodeToUtf8(const CATUnicodeString& value)
{
  const size_t capacity = static_cast<size_t>(value.GetLengthInChar() + 1) * 4 + 1;
  std::vector<char> buffer(capacity, 0);
  size_t byte_count = 0;
  value.ConvertToUTF8(&buffer[0], &byte_count);
  if (byte_count >= buffer.size())
    byte_count = buffer.size() - 1;
  buffer[byte_count] = 0;
  return std::string(&buffer[0], byte_count);
}

// 用途：从 CATICkeParm::Name 返回的限定路径中取参数叶名称，归属仍由真实 parent_of 图决定。
static std::string ParameterLeafName(const std::string& qualified_name)
{
  const std::string::size_type separator = qualified_name.find_last_of("/\\");
  return separator == std::string::npos ? qualified_name : qualified_name.substr(separator + 1);
}

// 用途：把 Automation Public 接口返回的 UTF-16 CATBSTR 转为独立 UTF-8 字符串。
static std::string BstrToUtf8(const CATBSTR value)
{
  if (!value) return "";
  const int wide_length = static_cast<int>(SysStringLen(value));
  if (wide_length == 0) return "";
  const int byte_length = WideCharToMultiByte(CP_UTF8, 0, value, wide_length,
                                               0, 0, 0, 0);
  if (byte_length <= 0) return "";
  std::vector<char> buffer(static_cast<size_t>(byte_length));
  WideCharToMultiByte(CP_UTF8, 0, value, wide_length, &buffer[0], byte_length, 0, 0);
  return std::string(&buffer[0], static_cast<size_t>(byte_length));
}

// 用途：从 CATIALength 的真实 Value 属性读取毫米数；调用者负责接口引用生命周期。
static bool ReadLengthValue(CATIALength* length, double& value)
{
  return length && SUCCEEDED(length->get_Value(value));
}

// 用途：从 CATIAAngle 的真实 Value 属性读取角度原值；R21 当前样件不依赖该可选字段。
static bool ReadAngleValue(CATIAAngle* angle, double& value)
{
  return angle && SUCCEEDED(angle->get_Value(value));
}

// 用途：把 SAFEARRAY(VARIANT) 的常见数值类型无损转换为 double。
static bool VariantToDouble(const CATVariant& value, double& output)
{
  if (V_VT(&value) == VT_R8) { output = V_R8(&value); return true; }
  if (V_VT(&value) == VT_R4) { output = V_R4(&value); return true; }
  if (V_VT(&value) == VT_I4) { output = V_I4(&value); return true; }
  if (V_VT(&value) == VT_I2) { output = V_I2(&value); return true; }
  return false;
}

// 用途：按 CATIAHole Automation 契约预分配三个 Variant，并读取原点或方向数组。
static bool ReadHoleVector(CATIAHole* hole, bool origin, double output[3])
{
  if (!hole) return false;
  CATSafeArrayVariant* array = SafeArrayCreateVector(VT_VARIANT, 0, 3);
  if (!array) return false;
  HRESULT read_result = E_FAIL;
  try
  {
    read_result = origin ? hole->GetOrigin(*array) : hole->GetDirection(*array);
  }
  catch (...)
  {
    SafeArrayDestroy(array);
    return false;
  }
  if (FAILED(read_result))
  {
    SafeArrayDestroy(array);
    return false;
  }
  CATVariant* values = 0;
  if (FAILED(SafeArrayAccessData(array, reinterpret_cast<void**>(&values))) || !values)
  {
    SafeArrayDestroy(array);
    return false;
  }
  bool valid = true;
  int index = 0;
  for (index = 0; index < 3; ++index)
    if (!VariantToDouble(values[index], output[index])) valid = false;
  SafeArrayUnaccessData(array);
  SafeArrayDestroy(array);
  return valid;
}

// 用途：把 R21 CatHoleType 的真实原始枚举映射为稳定 Schema 名称。
static std::string HoleTypeName(CatHoleType type, bool& known)
{
  known = true;
  if (type == catSimpleHole) return "simple";
  if (type == catTaperedHole) return "tapered";
  if (type == catCounterboredHole) return "counterbored";
  if (type == catCountersunkHole) return "countersunk";
  if (type == catCounterdrilledHole) return "counterdrilled";
  known = false;
  return "unknown";
}

// 用途：把 R21 CatLimitMode 的真实原始枚举映射为稳定 Schema 名称。
static std::string LimitModeName(CatLimitMode mode, bool& known)
{
  known = true;
  if (mode == catOffsetLimit) return "offset";
  if (mode == catUpToNextLimit) return "up_to_next";
  if (mode == catUpToLastLimit) return "up_to_last";
  if (mode == catUpToPlaneLimit) return "up_to_plane";
  if (mode == catUpToSurfaceLimit) return "up_to_surface";
  if (mode == catUpThruNextLimit) return "up_thru_next";
  known = false;
  return "unknown";
}

// 用途：创建未打开的 SessionGuard，并选定本 Batch 使用的稳定 Session 名称。
SessionGuard::SessionGuard() : _open(false), _name("CadParseMvpSession") {}

// 用途：在作用域结束时删除已成功创建的 CATIA Session。
SessionGuard::~SessionGuard()
{
  if (_open)
    Delete_Session(const_cast<char*>(_name.c_str()));
}

// 用途：调用本机 R21 Create_Session 初始化 CAA 运行环境。
// 成功后 _open 变为 true；失败时不取得清理责任，并在 error 中返回文档级原因。
bool SessionGuard::Open(std::string& error)
{
  CATSession* session = 0;
  const HRESULT result = Create_Session(const_cast<char*>(_name.c_str()), session);
  if (FAILED(result) || !session)
  {
    error = "CAA session initialization failed";
    return false;
  }
  _open = true;
  return true;
}

// 用途：创建空 DocumentGuard；0 表示当前不持有 CATDocument。
DocumentGuard::DocumentGuard() : _document(0) {}

// 用途：若文档已打开，则通过 CATDocumentServices::Remove 关闭并释放它。
DocumentGuard::~DocumentGuard()
{
  if (_document)
  {
    CATDocumentServices::Remove(*_document);
    _document = 0;
  }
}

// 用途：以不区分大小写方式检查路径是否以 .CATPart 结尾。
static bool EndsWithCatPart(const std::string& path)
{
  if (path.size() < 8) return false;
  std::string suffix = path.substr(path.size() - 8);
  std::transform(suffix.begin(), suffix.end(), suffix.begin(), ::tolower);
  return suffix == ".catpart";
}

// 用途：先校验文件存在性和扩展名，再通过 R21 文档服务以只读标志打开 CATPart。
// 成功时本守卫取得 _document 的关闭责任；失败返回 false 且不会留下半打开文档。
bool DocumentGuard::OpenReadOnly(const std::string& path, std::string& error)
{
  struct _stat file_status;
  if (_stat(path.c_str(), &file_status) != 0)
  {
    error = "input file does not exist";
    return false;
  }
  if (!EndsWithCatPart(path))
  {
    error = "input file is not a CATPart";
    return false;
  }
  const CATUnicodeString storage_name(path.c_str());
  const HRESULT result = CATDocumentServices::OpenDocument(storage_name, _document, TRUE);
  if (FAILED(result) || !_document)
  {
    error = "CATPart open failed";
    return false;
  }
  return true;
}

// 用途：返回当前文档的借用指针；所有权仍属于 DocumentGuard。
CATDocument* DocumentGuard::Get() const { return _document; }

// 适配没有 CATISpecObject 的静态节点，例如文档和容器入口。
class StaticObjectView : public INativeObjectView
{
public:
  // 用途：从已知常量和名称构造一个纯数据类型指纹。
  StaticObjectView(const char* native_type, const char* kind, const std::string& name)
  {
    _fingerprint.native_type = native_type;
    _fingerprint.container_kind = kind;
    _fingerprint.internal_name = name;
    _fingerprint.display_name = name;
  }

  // 用途：返回本视图持有的类型指纹只读引用。
  const TypeFingerprint& GetFingerprint() const { return _fingerprint; }

  // 用途：为静态节点补充通用 object_kind 属性；该操作不会访问 CAA 对象，因此总是成功。
  bool ReadBasicAttributes(FeatureRecord& output, std::string&) const
  {
    output.attributes["object_kind"] = _fingerprint.container_kind;
    return true;
  }

private:
  TypeFingerprint _fingerprint;
};

// CATISpecObject 的只读适配器；借用原生指针，只把可验证字段复制到 TypeFingerprint/IR。
class SpecObjectView : public INativeObjectView, public IStringParameterView, public INativeHoleView
{
public:
  // 用途：绑定一个借用 CATISpecObject，并立即构建稳定类型指纹。
  // context 用于记录指纹读取和接口探测产生的诊断/统计。
  SpecObjectView(CATISpecObject* spec, ParseContext& context) : _spec(spec)
  {
    BuildFingerprint(context);
  }

  // 用途：返回构造阶段已经复制完成的类型指纹。
  const TypeFingerprint& GetFingerprint() const { return _fingerprint; }

  // 用途：向参数 Decoder 暴露本适配器已有的 IStringParameterView，不依赖 /GR RTTI。
  const IStringParameterView* GetStringParameterView() const { return this; }

  // 用途：按能力标识暴露 CAA 原生适配器；新增能力不需要修改 Crawler 或对象视图接口。
  const INativeCapabilityView* FindCapability(const char* capability_id) const
  {
    return capability_id && std::string(capability_id) == "NativeHole" ? this : 0;
  }

  // 用途：读取经过 R21 PublicInterfaces 验证的基础状态和容器可访问性。
  // 任意 CAA 异常都转成 false+error，由 Registry 的 Generic/Opaque 链隔离。
  bool ReadBasicAttributes(FeatureRecord& output, std::string& error) const
  {
    if (!_spec)
    {
      error = "null CATISpecObject";
      return false;
    }
    try
    {
      output.update_status = _spec->IsUpToDate() ? "up_to_date" : "not_up_to_date";
      const CATIContainer_var container = _spec->GetFeatContainer();
      output.attributes["container_accessible"] = container == NULL_var ? "false" : "true";
      output.attributes["result_summary"] = "not_exposed_by_verified_mvp_interface";
      return true;
    }
    catch (...)
    {
      error = "CATISpecObject basic attribute read failed";
      return false;
    }
  }

  // 用途：查询 R21 Public CATICkeParm，验证其类型确为 String，再通过 Value()->AsString() 读取真实值。
  StringParameterReadStatus ReadStringParameter(ParameterValueData& parameter,
                                                std::string& error) const
  {
    if (!_spec)
    {
      error = "null CATISpecObject";
      return StringParameterInterfaceUnsupported;
    }
    CATICkeParm* raw_parameter = 0;
    try
    {
      const HRESULT query = _spec->QueryInterface(IID_CATICkeParm,
                                                   reinterpret_cast<void**>(&raw_parameter));
      if (FAILED(query) || !raw_parameter)
      {
        error = "CATICkeParm is not supported";
        return StringParameterInterfaceUnsupported;
      }
    }
    catch (...)
    {
      error = "CATICkeParm QueryInterface raised an exception";
      return StringParameterQueryException;
    }

    CaaInterfaceGuard<CATICkeParm> parameter_guard(raw_parameter);
    try
    {
      const CATICkeType_var parameter_type = raw_parameter->Type();
      if (parameter_type == NULL_var || static_cast<int>(parameter_type->IsaString()) == 0)
      {
        error = "CATICkeParm type is not String";
        return StringParameterInterfaceUnsupported;
      }
      const CATICkeInst_var value = raw_parameter->Value();
      if (value == NULL_var)
      {
        error = "CATICkeParm Value returned null";
        return StringParameterValueException;
      }
      parameter.parameter_kind = "string";
      parameter.value_status = "success";
      parameter.value_source = "typed_caa_value";
      parameter.value_text = UnicodeToUtf8(value->AsString());
    }
    catch (...)
    {
      error = "CATICkeParm typed String value read raised an exception";
      return StringParameterValueException;
    }
    // Name/Show/只读和隐藏状态是辅助信息；它们不可访问时不能否定已经成功取得的真实值。
    try { parameter.parameter_name = ParameterLeafName(UnicodeToUtf8(raw_parameter->Name())); }
    catch (...) { parameter.parameter_name = ParameterLeafName(_fingerprint.display_name); }
    try { parameter.raw_display_text = UnicodeToUtf8(raw_parameter->Show()); }
    catch (...) { parameter.raw_display_text.clear(); }
    try { parameter.is_read_only = static_cast<int>(raw_parameter->IsReadOnly()) == 0 ? "false" : "true"; }
    catch (...) { parameter.is_read_only = "unknown"; }
    try { parameter.is_hidden = static_cast<int>(raw_parameter->IsHidden()) == 0 ? "false" : "true"; }
    catch (...) { parameter.is_hidden = "unknown"; }
    return StringParameterReadSuccess;
  }

  // 用途：在当前 CATISpecObject 上直接查询 R21 Public CATIAHole，并读取真实设计参数。
  NativeHoleReadStatus ReadNativeHole(NativeHoleData& output, std::string& error) const
  {
    if (!_spec)
    {
      error = "null CATISpecObject";
      return NativeHoleInterfaceUnsupported;
    }
    CaaInterfaceGuard<CATIAHole> hole_guard;
    try
    {
      const HRESULT query = _spec->QueryInterface(IID_CATIAHole,
        reinterpret_cast<void**>(&hole_guard.Out()));
      if (FAILED(query) || !hole_guard.Get())
      {
        error = "CATIAHole is not supported";
        return NativeHoleInterfaceUnsupported;
      }
    }
    catch (...)
    {
      error = "CATIAHole QueryInterface raised an exception";
      return NativeHoleInterfaceQueryException;
    }

    CATIAHole* raw_hole = hole_guard.Get();
    output.semantic_kind = "part_design_hole";
    output.value_source = "typed_caa_value";
    output.interface_key = "CATIAHole";
    try
    {
      CatHoleType hole_type = catSimpleHole;
      if (FAILED(raw_hole->get_Type(hole_type)))
      {
        error = "CATIAHole.Type read failed";
        return NativeHoleRequiredValueReadException;
      }
      bool known_hole_type = false;
      output.hole_type_raw = static_cast<int>(hole_type);
      output.hole_type = HoleTypeName(hole_type, known_hole_type);
      output.field_status["hole_type"] = known_hole_type ? "success" : "unknown_enum";

      CaaInterfaceGuard<CATIALength> diameter_guard;
      if (FAILED(raw_hole->get_Diameter(diameter_guard.Out())) || !diameter_guard.Get())
      {
        error = "CATIAHole.Diameter interface read failed";
        return NativeHoleRequiredValueReadException;
      }
      if (!ReadLengthValue(diameter_guard.Get(), output.diameter_mm))
      {
        error = "CATIAHole.Diameter.Value read failed";
        return NativeHoleRequiredValueReadException;
      }
      output.field_status["diameter_mm"] = "success";

      if (!ReadHoleVector(raw_hole, true, output.origin_mm))
      {
        error = "CATIAHole.GetOrigin failed";
        return NativeHoleRequiredValueReadException;
      }
      if (!ReadHoleVector(raw_hole, false, output.direction))
      {
        error = "CATIAHole.GetDirection failed";
        return NativeHoleRequiredValueReadException;
      }
      output.field_status["origin_mm"] = "success";
      output.field_status["direction"] = "success";

      CaaInterfaceGuard<CATIALimit> limit_guard;
      if (FAILED(raw_hole->get_BottomLimit(limit_guard.Out())) || !limit_guard.Get())
      {
        error = "CATIAHole.BottomLimit read failed";
        return NativeHoleRequiredValueReadException;
      }
      CatLimitMode limit_mode = catOffsetLimit;
      if (FAILED(limit_guard.Get()->get_LimitMode(limit_mode)))
      {
        error = "CATIALimit.LimitMode read failed";
        return NativeHoleRequiredValueReadException;
      }
      bool known_limit_mode = false;
      output.bottom_limit.mode_raw = static_cast<int>(limit_mode);
      output.bottom_limit.mode = LimitModeName(limit_mode, known_limit_mode);
      output.field_status["bottom_limit.mode"] = known_limit_mode ? "success" : "unknown_enum";
      if (limit_mode == catOffsetLimit)
      {
        CaaInterfaceGuard<CATIALength> depth_guard;
        double depth = 0.0;
        if (FAILED(limit_guard.Get()->get_Dimension(depth_guard.Out())) || !depth_guard.Get())
        {
          error = "CATIALimit.Dimension read failed for offset Hole";
          return NativeHoleRequiredValueReadException;
        }
        if (!ReadLengthValue(depth_guard.Get(), depth))
        {
          error = "CATIALimit.Dimension.Value read failed for offset Hole";
          return NativeHoleRequiredValueReadException;
        }
        output.bottom_limit.depth_mm.Set(depth, "success");
      }
      else
        output.bottom_limit.depth_mm.Clear("not_applicable");

      output.head.kind = "none";
      output.head.diameter_mm.Clear("not_applicable");
      output.head.depth_mm.Clear("not_applicable");
      output.head.angle_deg.Clear("not_applicable");
      if (hole_type == catCounterboredHole || hole_type == catCounterdrilledHole)
      {
        CaaInterfaceGuard<CATIALength> head_diameter_guard;
        CaaInterfaceGuard<CATIALength> head_depth_guard;
        double head_diameter = 0.0;
        double head_depth = 0.0;
        if (FAILED(raw_hole->get_HeadDiameter(head_diameter_guard.Out())) ||
            !head_diameter_guard.Get())
        {
          error = "CATIAHole.HeadDiameter read failed";
          return NativeHoleRequiredValueReadException;
        }
        if (!ReadLengthValue(head_diameter_guard.Get(), head_diameter))
        {
          error = "CATIAHole.HeadDiameter.Value read failed";
          return NativeHoleRequiredValueReadException;
        }
        if (FAILED(raw_hole->get_HeadDepth(head_depth_guard.Out())) || !head_depth_guard.Get())
        {
          error = "CATIAHole.HeadDepth read failed";
          return NativeHoleRequiredValueReadException;
        }
        if (!ReadLengthValue(head_depth_guard.Get(), head_depth))
        {
          error = "CATIAHole.HeadDepth.Value read failed";
          return NativeHoleRequiredValueReadException;
        }
        output.head.kind = hole_type == catCounterboredHole ? "counterbore" : "counterdrill";
        output.head.diameter_mm.Set(head_diameter, "success");
        output.head.depth_mm.Set(head_depth, "success");
      }
      if (hole_type == catTaperedHole || hole_type == catCounterdrilledHole ||
          hole_type == catCountersunkHole)
      {
        CaaInterfaceGuard<CATIAAngle> head_angle_guard;
        double head_angle = 0.0;
        if (FAILED(raw_hole->get_HeadAngle(head_angle_guard.Out())) || !head_angle_guard.Get())
        {
          error = "CATIAHole.HeadAngle read failed";
          return NativeHoleRequiredValueReadException;
        }
        if (!ReadAngleValue(head_angle_guard.Get(), head_angle))
        {
          error = "CATIAHole.HeadAngle.Value read failed";
          return NativeHoleRequiredValueReadException;
        }
        if (hole_type == catTaperedHole) output.head.kind = "taper";
        else if (hole_type == catCountersunkHole) output.head.kind = "countersink";
        output.head.angle_deg.Set(head_angle, "typed_caa_angle_value");
      }
      if (hole_type == catCountersunkHole)
      {
        CaaInterfaceGuard<CATIALength> head_depth_guard;
        double head_depth = 0.0;
        if (FAILED(raw_hole->get_HeadDepth(head_depth_guard.Out())) || !head_depth_guard.Get() ||
            !ReadLengthValue(head_depth_guard.Get(), head_depth))
        {
          error = "CATIAHole countersink HeadDepth read failed";
          return NativeHoleRequiredValueReadException;
        }
        output.head.depth_mm.Set(head_depth, "success");
      }

      CatHoleThreadingMode threading_mode = catSmoothHoleThreading;
      if (FAILED(raw_hole->get_ThreadingMode(threading_mode)))
      {
        error = "CATIAHole.ThreadingMode read failed";
        return NativeHoleRequiredValueReadException;
      }
      output.thread.mode_raw = static_cast<int>(threading_mode);
      output.thread.enabled = threading_mode == catThreadedHoleThreading;
      output.field_status["thread.mode"] =
        (threading_mode == catThreadedHoleThreading || threading_mode == catSmoothHoleThreading) ?
        "success" : "unknown_enum";
      if (!output.thread.enabled)
      {
        output.thread.description.Clear("not_applicable");
        output.thread.diameter_mm.Clear("not_applicable");
        output.thread.depth_mm.Clear("not_applicable");
        output.thread.pitch_mm.Clear("not_applicable");
      }
      else
      {
        CaaInterfaceGuard<CATIALength> thread_diameter_guard;
        CaaInterfaceGuard<CATIALength> thread_depth_guard;
        CaaInterfaceGuard<CATIALength> thread_pitch_guard;
        CaaInterfaceGuard<CATIAStrParam> description_guard;
        double thread_diameter = 0.0;
        double thread_depth = 0.0;
        double thread_pitch = 0.0;
        if (FAILED(raw_hole->get_ThreadDiameter(thread_diameter_guard.Out())) ||
            !thread_diameter_guard.Get())
        {
          error = "CATIAHole.ThreadDiameter read failed";
          return NativeHoleRequiredValueReadException;
        }
        if (FAILED(raw_hole->get_ThreadDepth(thread_depth_guard.Out())) ||
            !thread_depth_guard.Get())
        {
          error = "CATIAHole.ThreadDepth read failed";
          return NativeHoleRequiredValueReadException;
        }
        if (FAILED(raw_hole->get_ThreadPitch(thread_pitch_guard.Out())) ||
            !thread_pitch_guard.Get())
        {
          error = "CATIAHole.ThreadPitch read failed";
          return NativeHoleRequiredValueReadException;
        }
        if (FAILED(raw_hole->get_HoleThreadDescription(description_guard.Out())) ||
            !description_guard.Get())
        {
          error = "CATIAHole.HoleThreadDescription read failed";
          return NativeHoleRequiredValueReadException;
        }
        if (!ReadLengthValue(thread_diameter_guard.Get(), thread_diameter) ||
            !ReadLengthValue(thread_depth_guard.Get(), thread_depth) ||
            !ReadLengthValue(thread_pitch_guard.Get(), thread_pitch))
        {
          error = "CATIAHole threaded numeric Value read failed";
          return NativeHoleRequiredValueReadException;
        }
        CaaBstrGuard description;
        if (FAILED(description_guard.Get()->get_Value(description.Out())))
        {
          error = "CATIAHole thread description Value read failed";
          return NativeHoleRequiredValueReadException;
        }
        const std::string description_utf8 = BstrToUtf8(description.Get());
        output.thread.diameter_mm.Set(thread_diameter, "success");
        output.thread.depth_mm.Set(thread_depth, "success");
        output.thread.pitch_mm.Set(thread_pitch, "success");
        output.thread.description.Set(description_utf8, "success");
      }

      CaaBstrGuard alias;
      if (SUCCEEDED(raw_hole->get_Name(alias.Out())))
      {
        output.has_automation_alias = true;
        output.automation_alias = BstrToUtf8(alias.Get());
        output.automation_alias_status = "success";
      }
      else
        output.automation_alias_status = "automation_alias_unavailable";
    }
    catch (...)
    {
      error = "CATIAHole required value read raised an exception";
      return NativeHoleRequiredValueReadException;
    }
    return NativeHoleReadSuccess;
  }

private:
  // R21 的受控接口探测器，只接受代码中显式列出的已验证接口键。
  class R21InterfaceProbeService : public InterfaceProbeService
  {
  public:
    // 用途：绑定待探测的借用 CATISpecObject，不增加也不释放其引用计数。
    explicit R21InterfaceProbeService(CATISpecObject* spec) : _spec(spec) {}

    // 用途：探测一个白名单接口；成功时追加键并立刻释放 QueryInterface 返回的临时引用。
    // 未知 key 不会被猜测，直接计入探测失败。
    std::string Probe(const char* key, TypeFingerprint& fingerprint, ParseStatistics& statistics)
    {
      if (std::strcmp(key, "CATISpecObject") == 0)
      {
        fingerprint.supported_interface_keys.push_back(key);
        statistics.RecordProbe(key, fingerprint.native_type, "unselected", "supported");
        return "supported";
      }
      const IID* iid = 0;
      if (std::strcmp(key, "CATIPrtPart") == 0) iid = &IID_CATIPrtPart;
      else if (std::strcmp(key, "CATIContainer") == 0) iid = &IID_CATIContainer;
      else if (std::strcmp(key, "CATIPrtContainer") == 0) iid = &IID_CATIPrtContainer;
      else if (std::strcmp(key, "CATIAHole") == 0) iid = &IID_CATIAHole;
      if (!iid)
      {
        statistics.RecordProbe(key, fingerprint.native_type, "unselected", "not_attempted");
        return "not_attempted";
      }
      void* result = 0;
      try
      {
        if (SUCCEEDED(_spec->QueryInterface(*iid, &result)) && result)
        {
          fingerprint.supported_interface_keys.push_back(key);
          // QueryInterface 成功会增加引用计数；这里只验证存在性，必须立即配对 Release。
          static_cast<CATBaseUnknown*>(result)->Release();
          statistics.RecordProbe(key, fingerprint.native_type, "unselected", "supported");
          return "supported";
        }
      }
      catch (...)
      {
        statistics.RecordProbe(key, fingerprint.native_type, "unselected", "exception");
        return "exception";
      }
      statistics.RecordProbe(key, fingerprint.native_type, "unselected", "unsupported");
      return "unsupported";
    }

  private:
    CATISpecObject* _spec;
  };

  // 用途：从 CATISpecObject 读取 StartUp/SuperType/名称，并执行固定接口白名单探测。
  // 任何不可用字段只产生 warning；未验证的 native runtime type 保持为空，不进行猜测。
  void BuildFingerprint(ParseContext& context)
  {
    if (!_spec) return;
    // TODO(R21_API_VERIFY)：尚未确认 R21 公开接口中存在有文档依据的原生运行时类型读取方法。
    try
    {
      _fingerprint.startup_type = UnicodeToUtf8(_spec->GetType());
      const std::string super_type = UnicodeToUtf8(_spec->GetSuperType());
      if (!super_type.empty()) _fingerprint.super_types.push_back(super_type);
      _fingerprint.internal_name = UnicodeToUtf8(_spec->GetName());
      _fingerprint.display_name = UnicodeToUtf8(_spec->GetDisplayName());
      _fingerprint.container_kind = "feature";
    }
    catch (...)
    {
      context.AddDiagnostic("warning", "fingerprint", "SPEC_FINGERPRINT_READ_FAILED",
                            "one or more CATISpecObject type fields were unavailable", "");
    }
    R21InterfaceProbeService probes(_spec);
    probes.Probe("CATISpecObject", _fingerprint, context.statistics);
    probes.Probe("CATIPrtPart", _fingerprint, context.statistics);
    probes.Probe("CATIContainer", _fingerprint, context.statistics);
    probes.Probe("CATIPrtContainer", _fingerprint, context.statistics);
    // Hole 专用探测只对已预筛选候选执行；Typed Decoder 随后仍会再次查询并读取必需值。
    if (_fingerprint.startup_type == "Hole")
      probes.Probe("CATIAHole", _fingerprint, context.statistics);
    if (std::find(_fingerprint.supported_interface_keys.begin(),
                  _fingerprint.supported_interface_keys.end(), "CATIPrtPart") !=
        _fingerprint.supported_interface_keys.end())
      _fingerprint.container_kind = "part";
  }

  CATISpecObject* _spec;
  TypeFingerprint _fingerprint;
};

// 基础 Typed Decoder：封装所有核心节点共有的“读取基础属性并标记 typed success”行为。
class CoreDecoder : public IFeatureDecoder
{
public:
  // 用途：保存由静态字符串提供的稳定 ID 和显式优先级。
  CoreDecoder(const char* id, int priority) : _id(id), _priority(priority) {}
  // 用途：返回构造时绑定的 Decoder ID；Core Decoder 使用字符串常量，生命周期覆盖整个进程。
  const char* GetDecoderId() const { return _id; }
  // 用途：返回用于 Registry 决胜的显式优先级。
  int GetPriority() const { return _priority; }
  // 用途：执行 Typed Decoder 的公共读取逻辑；失败时交回 Registry 继续 Generic/Opaque 兜底。
  DecodeResult Decode(const INativeObjectView& view, ParseContext& context, FeatureRecord& output)
  {
    std::string error;
    if (!view.ReadBasicAttributes(output, error))
      return DecodeResult(false, "failed", error.c_str());
    output.decoder_id = _id;
    output.decode_level = "typed";
    output.decode_status = "success";
    return DecodeResult(true, "typed");
  }

protected:
  const char* _id;
  int _priority;
};

// 文档根节点 Decoder，依据 crawler 明确赋予的 container_kind 匹配。
class DocumentDecoder : public CoreDecoder
{
public:
  // 用途：创建优先级 400、稳定 ID 为 document 的 Decoder。
  DocumentDecoder() : CoreDecoder("document", 400) {}
  // 用途：只匹配 container_kind 为 document 的静态文档视图。
  bool Match(const TypeFingerprint& fp, const INativeObjectView&) const
  { return fp.container_kind == "document"; }
};

// Part Decoder，优先使用已验证 CATIPrtPart 接口键而不是显示名称。
class PartDecoder : public CoreDecoder
{
public:
  // 用途：创建高优先级 Part Decoder，使接口证据优先于通用容器匹配。
  PartDecoder() : CoreDecoder("part", 700) {}
  // 用途：检查 supported_interface_keys 中是否存在 CATIPrtPart。
  bool Match(const TypeFingerprint& fp, const INativeObjectView&) const
  { return std::find(fp.supported_interface_keys.begin(), fp.supported_interface_keys.end(),
                     "CATIPrtPart") != fp.supported_interface_keys.end(); }
};

// 已验证容器入口的 Typed Decoder。
class ContainerDecoder : public CoreDecoder
{
public:
  // 用途：创建 ID 为 container、优先级 350 的 Decoder。
  ContainerDecoder() : CoreDecoder("container", 350) {}
  // 用途：匹配 crawler 明确标记为 container 的静态入口节点。
  bool Match(const TypeFingerprint& fp, const INativeObjectView&) const
  { return fp.container_kind == "container"; }
};

// Body 基础 Decoder；R21 PublicInterfaces 未提供已确认 marker，因此只使用保守 StartUp 类型匹配。
class BodyDecoder : public CoreDecoder
{
public:
  // 用途：创建 ID 为 body、优先级 500 的 Decoder。
  BodyDecoder() : CoreDecoder("body", 500) {}
  // TODO(R21_API_VERIFY)：已安装的公开接口中未找到 CATIBody 标记接口。
  // 用途：匹配本机资料中已知的 Body/MechanicalTool StartUp 类型文本。
  bool Match(const TypeFingerprint& fp, const INativeObjectView&) const
  { return fp.startup_type == "Body" || fp.startup_type == "MechanicalTool"; }
};

// HybridBody 基础 Decoder；同样不假设不存在证据的专用 marker 接口。
class HybridBodyDecoder : public CoreDecoder
{
public:
  // 用途：创建 ID 为 hybrid_body、优先级 500 的 Decoder。
  HybridBodyDecoder() : CoreDecoder("hybrid_body", 500) {}
  // TODO(R21_API_VERIFY)：已安装的公开接口中未找到 CATIHybridBody 标记接口。
  // 用途：匹配已确认的 HybridBody/GeometricalSet StartUp 类型文本。
  bool Match(const TypeFingerprint& fp, const INativeObjectView&) const
  { return fp.startup_type == "HybridBody" || fp.startup_type == "GeometricalSet"; }
};

// 用途：创建 MVP 的五个基础 Typed Decoder，同时登记到 Registry 和所有权 vector。
// Registry 仅借用指针；owned_decoders 是唯一负责最终 delete 的容器。
void RegisterCoreDecoders(FeatureTypeRegistry& registry,
                          std::vector<IFeatureDecoder*>& owned_decoders)
{
  owned_decoders.push_back(new KnowledgewareStringParameterDecoder());
  owned_decoders.push_back(new NativeHoleDecoder());
  owned_decoders.push_back(new DocumentDecoder());
  owned_decoders.push_back(new PartDecoder());
  owned_decoders.push_back(new ContainerDecoder());
  owned_decoders.push_back(new BodyDecoder());
  owned_decoders.push_back(new HybridBodyDecoder());
  // C++03 没有范围 for，使用 iterator 按固定顺序注册；匹配结果仍不依赖注册顺序。
  std::vector<IFeatureDecoder*>::iterator it = owned_decoders.begin();
  for (; it != owned_decoders.end(); ++it) registry.Register(*it);
}

// 用途：释放 RegisterCoreDecoders 创建的全部 Decoder，并清空所有权容器。
void DeleteCoreDecoders(std::vector<IFeatureDecoder*>& owned_decoders)
{
  std::vector<IFeatureDecoder*>::iterator it = owned_decoders.begin();
  for (; it != owned_decoders.end(); ++it) delete *it;
  owned_decoders.clear();
}

// 用途：创建一次遍历所需的 Crawler，并以引用保存 Registry、上下文和两个输出集合。
// 这些引用不转移所有权，调用者必须保证它们覆盖整个 Crawl 生命周期。
UniversalFeatureCrawler::UniversalFeatureCrawler(FeatureTypeRegistry& registry, ParseContext& context,
                                                 std::vector<FeatureRecord>& features,
                                                 std::vector<RelationRecord>& relations)
  : _registry(registry), _context(context), _features(features), _relations(relations)
{
}

// 用途：先为对象建立基础 FeatureRecord，再执行 Decoder，并按 parent_id 建立正式关系。
// 返回新分配的稳定 feature_id，供递归子节点作为 parent_id 使用。
std::string UniversalFeatureCrawler::AddObject(INativeObjectView& view,
                                               const std::string& parent_id,
                                               const std::string& tree_path,
                                               long native_enumeration_index,
                                               long container_enumeration_index)
{
  FeatureRecord record;
  record.feature_id = _ids.Next();
  record.parent_id = parent_id;
  record.native_enumeration_index = native_enumeration_index;
  record.container_enumeration_index = container_enumeration_index;
  record.traversal_index = static_cast<long>(_features.size() + 1);
  record.tree_path = tree_path;
  record.update_status = "unknown";
  record.visibility = "unknown";
  // 即使 Decode 随后失败，类型观察和基础记录也已经建立，满足“不丢对象”的约束。
  _catalog.Observe(view.GetFingerprint());
  _registry.DecodeObject(view, _context, record);
  if (record.update_status == "not_up_to_date")
  {
    ++_context.statistics.not_up_to_date_count;
    const std::string type = record.fingerprint.native_type.empty() ?
      record.fingerprint.startup_type : record.fingerprint.native_type;
    ++_context.statistics.not_up_to_date_by_native_type[type.empty() ? "unknown" : type];
    ++_context.statistics.not_up_to_date_by_decoder[record.decoder_id];
    _context.statistics.not_up_to_date_feature_ids.push_back(record.feature_id);
  }
  _features.push_back(record);
  if (!parent_id.empty())
  {
    RelationRecord relation;
    relation.kind = "parent_of";
    relation.from_id = parent_id;
    relation.to_id = record.feature_id;
    _relations.push_back(relation);
    relation.kind = "contains";
    _relations.push_back(relation);
  }
  return record.feature_id;
}

// 用途：递归访问一个规格对象，严格保留 ListComponents 返回的原生顺序。
// visited 以运行期指针识别循环，但指针仅用于本次遍历控制，绝不写入输出。
bool UniversalFeatureCrawler::VisitSpec(CATISpecObject* spec, const std::string& parent_id,
                                        const std::string& parent_path,
                                        long native_enumeration_index,
                                        long container_enumeration_index)
{
  // 重复到达同一个原生对象时直接返回，防止循环引用或多入口造成无限递归。
  if (!spec || _visited.find(spec) != _visited.end()) return true;
  _visited.insert(spec);

  try
  {
    SpecObjectView view(spec, _context);
    const TypeFingerprint& fp = view.GetFingerprint();
    _unknown_types.Observe(fp);
    _context.statistics.unknown_native_type_count = static_cast<long>(_unknown_types.Count());
    std::string segment = fp.display_name.empty() ? fp.internal_name : fp.display_name;
    if (segment.empty()) segment = fp.startup_type.empty() ? "unnamed" : fp.startup_type;
    const std::string path = parent_path + "/" + segment;
    const std::string id = AddObject(view, parent_id, path, native_enumeration_index,
                                     container_enumeration_index);

    CATListValCATISpecObject_var* children = spec->ListComponents();
    if (!children) return true;
    // ListComponents 返回堆对象，立即建立守卫，保证后续任何异常路径都能 delete。
    SpecListGuard children_guard(children);
    int index = 0;
    for (index = 1; index <= children->Size(); ++index)
    {
      CATISpecObject_var child = (*children)[index];
      if (child != NULL_var)
      {
        CATISpecObject* child_pointer = child;
        VisitSpec(child_pointer, id, path, index, container_enumeration_index);
      }
    }
    return true;
  }
  catch (...)
  {
    // 对象级异常转成诊断并返回 false；上层可决定入口失败是否为文档级致命错误。
    _context.AddDiagnostic("warning", "discovery", "OBJECT_TRAVERSAL_FAILED",
                           "CATISpecObject traversal failed; scan continued", parent_id);
    return false;
  }
}

// 用途：从 CATDocument 根开始执行 MVP 完整发现链路，并枚举已验证 Part 容器与规格对象入口。
// document 是 DocumentGuard 拥有的借用指针；函数不关闭文档。入口级失败通过 error 返回 false。
bool UniversalFeatureCrawler::Crawl(CATDocument* document, std::string& error)
{
  if (!document)
  {
    error = "null CATDocument";
    return false;
  }
  try
  {
  // 文档和容器不是 CATISpecObject，先用 StaticObjectView 为它们建立同样完整的基础 IR。
  StaticObjectView document_view("CATDocument", "document", UnicodeToUtf8(document->DisplayName()));
  const std::string document_id = AddObject(document_view, "", "/document", 0, 0);

  CATInit* init = 0;
  // QueryInterface 成功会返回持有引用；守卫必须在紧邻成功检查后接管它。
  if (FAILED(document->QueryInterface(IID_CATInit, reinterpret_cast<void**>(&init))) || !init)
  {
    error = "CATInit is unavailable on CATPart document";
    return false;
  }
  CaaInterfaceGuard<CATInit> init_guard(init);
  // GetRootContainer 返回的 CATBaseUnknown 引用由 root_guard 负责释放。
  CATBaseUnknown* root = init->GetRootContainer("CATIPrtContainer");
  if (!root)
  {
    error = "CATIPrtContainer root is unavailable";
    return false;
  }
  CaaInterfaceGuard<CATBaseUnknown> root_guard(root);

  CATIPrtContainer* part_container = 0;
  const HRESULT root_result = root->QueryInterface(IID_CATIPrtContainer,
                                                    reinterpret_cast<void**>(&part_container));
  if (FAILED(root_result) || !part_container)
  {
    error = "CATIPrtContainer query failed";
    return false;
  }
  CaaInterfaceGuard<CATIPrtContainer> part_container_guard(part_container);

  // 把已验证的 Part Spec Container 作为独立 IR 节点，后续 Feature 都挂在它下面。
  StaticObjectView container_view("CATIPrtContainer", "container", "PartSpecContainer");
  const std::string container_id = AddObject(container_view, document_id,
                                              "/document/PartSpecContainer", 1, 1);
  ++_context.statistics.container_count;

  CATISpecObject_var part = NULL_var;
  // _var 是 CAA 智能引用包装，离开作用域时自动管理 GetPart 返回对象的引用计数。
  try
  {
    part = part_container->GetPart();
  }
  catch (...)
  {
    _context.AddDiagnostic("warning", "discovery", "PART_ENTRY_EXCEPTION",
                           "CATIPrtContainer::GetPart raised an exception", container_id);
    error = "Part root access failed";
    return false;
  }
  if (part != NULL_var)
  {
    CATISpecObject* part_pointer = part;
    if (!VisitSpec(part_pointer, container_id, "/document/PartSpecContainer", 1, 1))
    {
      error = "Part root traversal failed";
      return false;
    }
  }
  else
  {
    _context.AddDiagnostic("warning", "discovery", "PART_ENTRY_UNAVAILABLE",
                           "CATIPrtContainer::GetPart returned null", container_id);
    error = "Part root is unavailable";
    return false;
  }

  CATIContainer* generic_container = 0;
  // CATIContainer 是补充入口：存在时枚举当前容器成员，不存在时仅记录 info 而不猜测替代 API。
  if (SUCCEEDED(root->QueryInterface(IID_CATIContainer,
                                     reinterpret_cast<void**>(&generic_container))) && generic_container)
  {
    CaaInterfaceGuard<CATIContainer> generic_container_guard(generic_container);
    try
    {
      SEQUENCE(CATBaseUnknown_ptr) members;
      // 先建立序列守卫，再调用枚举；异常时已经返回的成员引用也能被释放。
      BaseUnknownSequenceGuard members_guard(members);
      const CATLONG32 count = generic_container->ListMembersHere("CATISpecObject", members);
      CATLONG32 index = 0;
      for (index = 0; index < count; ++index)
      {
        CATBaseUnknown* member = members[index];
        if (!member) continue;
        CATISpecObject* member_spec = 0;
        if (SUCCEEDED(member->QueryInterface(IID_CATISpecObject,
                                             reinterpret_cast<void**>(&member_spec))) && member_spec)
        {
          // 临时 QueryInterface 引用由局部守卫释放；立即按枚举器原始位置访问。
          CaaInterfaceGuard<CATISpecObject> member_spec_guard(member_spec);
          VisitSpec(member_spec, container_id, "/document/PartSpecContainer",
                    static_cast<long>(index + 1), 1);
        }
      }
    }
    catch (...)
    {
      _context.AddDiagnostic("warning", "discovery", "CONTAINER_ENUMERATION_EXCEPTION",
                             "CATIContainer member enumeration failed", container_id);
      error = "supplemental container enumeration failed";
      return false;
    }
  }
  else
    _context.AddDiagnostic("info", "discovery", "APPLICATIVE_CONTAINER_UNAVAILABLE",
                           "root container does not expose CATIContainer", container_id);

  if (_context.statistics.not_up_to_date_count > 0)
  {
    std::ostringstream message;
    message << _context.statistics.not_up_to_date_count
            << " enumerated objects are not up to date; see coverage feature IDs";
    _context.AddDiagnostic("warning", "document", "MODEL_CONTAINS_STALE_OBJECTS",
                           message.str().c_str(), document_id);
  }

  _context.statistics.relation_count = static_cast<long>(_relations.size());
  return true;
  }
  catch (...)
  {
    // 最外层 catch 是文档级安全网；所有已创建的 RAII 守卫仍会按栈展开顺序执行清理。
    error = "CAA traversal raised an unhandled exception";
    return false;
  }
}
}
