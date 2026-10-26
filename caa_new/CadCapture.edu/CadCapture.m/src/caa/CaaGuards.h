/* 提供不可复制的 CAA 接口引用守卫，在作用域结束时调用 Release。 */
#ifndef CADCAPTURE_CAA_CAAGUARDS_H
#define CADCAPTURE_CAA_CAAGUARDS_H

namespace cadcapture {

template <class T>
class CaaInterfaceGuard
{
public:
  CaaInterfaceGuard() : _ptr(0) {}
  explicit CaaInterfaceGuard(T* ptr) : _ptr(ptr) {}
  ~CaaInterfaceGuard() { if (_ptr) _ptr->Release(); }
  T* Get() const { return _ptr; }
  /* 供首次 QueryInterface 写出引用；覆盖已有非空指针前须由调用方释放旧引用。 */
  T*& Out() { return _ptr; }

private:
  CaaInterfaceGuard(const CaaInterfaceGuard&);
  CaaInterfaceGuard& operator=(const CaaInterfaceGuard&);
  T* _ptr;
};

}

#endif
