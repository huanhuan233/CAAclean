/* 声明 CAA 能力查询入口和自动释放接口引用的租约类型。 */
#ifndef CADCAPTURE_CAA_CAACAPABILITYBROKER_H
#define CADCAPTURE_CAA_CAACAPABILITYBROKER_H

#include "model/ReconstructionPackage.h"
#include <CATBaseUnknown.h>
#include <CATErrorDef.h>
#include <map>
#include <string>

namespace cadcapture {

/* 区分可用、不支持、当前对象缺失和调用异常，供诊断保留失败原因。 */
enum CapabilityStatus
{
  CapabilityAvailable,
  CapabilityUnsupported,
  CapabilityUnavailable,
  CapabilityException
};

/* 独占一份接口引用并自动释放；As 只做指针转换，类型必须与获取接口一致。 */
class CaaCapabilityLease
{
public:
  CaaCapabilityLease();
  ~CaaCapabilityLease();

  bool IsAvailable() const;
  CapabilityStatus Status() const;
  void Reset(CATBaseUnknown* value, CapabilityStatus status);
  void Release();

  template <class T>
  T* As() const
  {
    return reinterpret_cast<T*>(_value);
  }

private:
  CaaCapabilityLease(const CaaCapabilityLease&);
  CaaCapabilityLease& operator=(const CaaCapabilityLease&);

  CATBaseUnknown* _value;
  CapabilityStatus _status;
};

/* 统一记录能力证据；Query 每次实际查询对象，缓存不替代对象接口探测。 */
class CaaCapabilityBroker
{
public:
  CapabilityStatus Check(const std::string& capability,
                         ReconstructionPackage& package);

  /* 查询成功后 out 带有待释放的接口引用；直接调用者负责 Release。 */
  template <class T>
  CapabilityStatus Query(CATBaseUnknown* object,
                         const IID& interface_id,
                         const std::string& capability,
                         const std::string& subject_id,
                         ReconstructionPackage& package,
                         T*& out)
  {
    out = 0;
    if (!object)
    {
      _cache[subject_id + "|" + capability] = CapabilityUnavailable;
      Record(capability, subject_id, CapabilityUnavailable, "native object is null", package);
      return CapabilityUnavailable;
    }
    try
    {
      if (FAILED(object->QueryInterface(interface_id, reinterpret_cast<void**>(&out))) || !out)
      {
        _cache[subject_id + "|" + capability] = CapabilityUnsupported;
        Record(capability, subject_id, CapabilityUnsupported, "QueryInterface returned unsupported", package);
        return CapabilityUnsupported;
      }
      _cache[subject_id + "|" + capability] = CapabilityAvailable;
      Record(capability, subject_id, CapabilityAvailable, "QueryInterface succeeded", package);
      return CapabilityAvailable;
    }
    catch (...)
    {
      out = 0;
      _cache[subject_id + "|" + capability] = CapabilityException;
      Record(capability, subject_id, CapabilityException, "QueryInterface raised an exception", package);
      return CapabilityException;
    }
  }

  /* 把成功查询取得的接口引用交给租约管理，并重置租约的旧状态。 */
  template <class T>
  CapabilityStatus Acquire(CATBaseUnknown* object,
                           const IID& interface_id,
                           const std::string& capability,
                           const std::string& subject_id,
                           ReconstructionPackage& package,
                           CaaCapabilityLease& lease)
  {
    T* out = 0;
    const CapabilityStatus status = Query<T>(object, interface_id, capability, subject_id, package, out);
    if (status == CapabilityAvailable)
      lease.Reset(reinterpret_cast<CATBaseUnknown*>(out), status);
    else
      lease.Reset(0, status);
    return status;
  }

  void Record(const std::string& capability,
              const std::string& subject_id,
              CapabilityStatus status,
              const std::string& message,
              ReconstructionPackage& package);

private:
  std::map<std::string, CapabilityStatus> _cache;
};

}

#endif
