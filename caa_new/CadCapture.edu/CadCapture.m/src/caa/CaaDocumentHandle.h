#ifndef CADCAPTURE_CAA_CAADOCUMENTHANDLE_H
#define CADCAPTURE_CAA_CAADOCUMENTHANDLE_H

#include <string>

namespace cadcapture {

class CaaDocumentHandle
{
public:
  CaaDocumentHandle();
  ~CaaDocumentHandle();

  bool OpenReadOnly(const std::string& path, std::string& error);
  void Close();
  bool IsOpen() const;

  void* NativeDocumentForCaaOnly() const;
  std::string DisplayName() const;

private:
  CaaDocumentHandle(const CaaDocumentHandle&);
  CaaDocumentHandle& operator=(const CaaDocumentHandle&);

  void* _document;
};

}

#endif
