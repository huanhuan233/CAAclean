#ifndef CADCAPTURE_RECONSTRUCTION_RECONSTRUCTIONVALIDATOR_H
#define CADCAPTURE_RECONSTRUCTION_RECONSTRUCTIONVALIDATOR_H

#include "model/ReconstructionPackage.h"
#include <string>

namespace cadcapture {

class ReconstructionValidator
{
public:
  bool Validate(const ReconstructionPackage& package, std::string& error) const;
};

}

#endif
