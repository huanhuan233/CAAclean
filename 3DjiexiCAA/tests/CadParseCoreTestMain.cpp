// 本文件是 VS2008 无许可证测试的最小进程入口，只负责运行 SelfTestSuite 并设置退出码。
#include "CadParseContracts.h"

#include <iostream>

// 用途：执行全部核心自测；成功输出提示并返回 0，任一失败返回 1。
// 参数名被省略，因为测试入口不读取命令行；这仍是标准 C/C++ main 签名。
int main(int, char**)
{
  cadparse::SelfTestSuite suite;
  const int failures = suite.RunAll();
  if (failures != 0)
  {
    std::cerr << "self-test failures: " << failures << std::endl;
    return 1;
  }
  std::cout << "self-test passed" << std::endl;
  return 0;
}
