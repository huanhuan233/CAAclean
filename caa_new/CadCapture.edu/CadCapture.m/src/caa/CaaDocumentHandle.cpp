#include "caa/CaaDocumentHandle.h"

#include <CATDocument.h>
#include <CATDocumentServices.h>
#include <CATErrorDef.h>
#include <CATUnicodeString.h>
#include <algorithm>
#include <cctype>
#include <sys/stat.h>
#include <vector>

namespace cadcapture {

static std::string CaaUnicodeToUtf8(const CATUnicodeString& value)
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

static std::string LowerSuffix(const std::string& path, size_t count)
{
  if (path.size() < count)
    return "";
  std::string suffix = path.substr(path.size() - count);
  std::transform(suffix.begin(), suffix.end(), suffix.begin(), static_cast<int (*)(int)>(std::tolower));
  return suffix;
}

static bool IsSupportedNativeDocument(const std::string& path)
{
  return LowerSuffix(path, 8) == ".catpart" || LowerSuffix(path, 11) == ".catproduct";
}

CaaDocumentHandle::CaaDocumentHandle() : _document(0) {}

CaaDocumentHandle::~CaaDocumentHandle()
{
  Close();
}

bool CaaDocumentHandle::OpenReadOnly(const std::string& path, std::string& error)
{
  struct _stat file_status;
  if (_stat(path.c_str(), &file_status) != 0)
  {
    error = "input file does not exist";
    return false;
  }
  if (!IsSupportedNativeDocument(path))
  {
    error = "input file is not a CATPart or CATProduct";
    return false;
  }

  CATDocument* document = 0;
  const CATUnicodeString storage_name(path.c_str());
  const HRESULT result = CATDocumentServices::OpenDocument(storage_name, document, TRUE);
  if (FAILED(result) || !document)
  {
    error = "CATIA document open failed";
    return false;
  }

  Close();
  _document = document;
  return true;
}

void CaaDocumentHandle::Close()
{
  if (_document)
  {
    CATDocument* document = static_cast<CATDocument*>(_document);
    CATDocumentServices::Remove(*document);
    _document = 0;
  }
}

bool CaaDocumentHandle::IsOpen() const
{
  return _document != 0;
}

void* CaaDocumentHandle::NativeDocumentForCaaOnly() const
{
  return _document;
}

std::string CaaDocumentHandle::DisplayName() const
{
  if (!_document)
    return "";
  CATDocument* document = static_cast<CATDocument*>(_document);
  return CaaUnicodeToUtf8(document->DisplayName());
}

}
