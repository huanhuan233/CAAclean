#include "CadParseContracts.h"

#include <iostream>

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
