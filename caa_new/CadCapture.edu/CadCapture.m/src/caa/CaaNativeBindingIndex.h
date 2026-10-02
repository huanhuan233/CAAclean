#ifndef CADCAPTURE_CAA_CAANATIVEBINDINGINDEX_H
#define CADCAPTURE_CAA_CAANATIVEBINDINGINDEX_H

#include "model/ReconstructionPackage.h"
#include <CATISpecObject.h>
#include <map>
#include <string>
#include <vector>

namespace cadcapture {

// 中文：索引只在打开文档期间存在；关闭文档前销毁，不把 CAA 指针保存进持久模型。
class CaaNativeBindingIndex
{
public:
  // 中文：一次建立 ID 和指针双向索引，可限制到本次新登记的原生绑定。
  explicit CaaNativeBindingIndex(const ReconstructionPackage& package, size_t first_binding = 0)
  {
    size_t i;
    for (i = first_binding; i < package.native_object_bindings.size(); ++i)
    {
      const NativeObjectBinding& binding = package.native_object_bindings[i];
      CATISpecObject* spec = static_cast<CATISpecObject*>(binding.native_spec_object);
      if (!spec || binding.object_id.empty())
        continue;
      _by_object_id[binding.object_id] = spec;
      _by_pointer[spec] = binding.object_id;
      _ordered.push_back(Binding(spec, binding.object_id));
    }
  }

  // 中文：按对象 ID 在对数时间查找仍有效的原生规格对象。
  CATISpecObject* FindSpec(const std::string& object_id) const
  {
    std::map<std::string, CATISpecObject*>::const_iterator found = _by_object_id.find(object_id);
    return found == _by_object_id.end() ? 0 : found->second;
  }

  // 中文：先用指针和已缓存别名命中，仅对首次未知引用执行 CATIA 等价判断。
  std::string Resolve(const CATISpecObject_var& reference)
  {
    if (reference == NULL_var)
      return "";
    CATISpecObject* pointer = reference;
    std::map<CATISpecObject*, std::string>::const_iterator direct = _by_pointer.find(pointer);
    if (direct != _by_pointer.end())
      return direct->second;
    std::map<CATISpecObject*, std::string>::const_iterator cached = _aliases.find(pointer);
    if (cached != _aliases.end())
      return cached->second;
    size_t i;
    for (i = 0; i < _ordered.size(); ++i)
    {
      try
      {
        if (_ordered[i].spec->IsEqual(reference))
        {
          _aliases[pointer] = _ordered[i].object_id;
          return _ordered[i].object_id;
        }
      }
      catch (...)
      {
        // 中文：单个损坏接口不能终止其余引用的身份解析。
      }
    }
    _aliases[pointer] = "";
    return "";
  }

private:
  struct Binding
  {
    CATISpecObject* spec;
    std::string object_id;
    Binding(CATISpecObject* source, const std::string& id) : spec(source), object_id(id) {}
  };

  std::map<std::string, CATISpecObject*> _by_object_id;
  std::map<CATISpecObject*, std::string> _by_pointer;
  std::map<CATISpecObject*, std::string> _aliases;
  std::vector<Binding> _ordered;
};

}

#endif
