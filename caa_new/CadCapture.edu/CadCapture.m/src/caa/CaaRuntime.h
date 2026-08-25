#ifndef CADCAPTURE_CAA_CAARUNTIME_H
#define CADCAPTURE_CAA_CAARUNTIME_H

#include <string>

namespace cadcapture {

class CaaRuntime
{
public:
  CaaRuntime();
  ~CaaRuntime();

  bool Open(std::string& error);
  void Close();
  bool IsOpen() const;

private:
  CaaRuntime(const CaaRuntime&);
  CaaRuntime& operator=(const CaaRuntime&);

  bool _open;
  std::string _session_name;
};

}

#endif
