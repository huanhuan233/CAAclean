#ifndef CADCAPTURE_RECONSTRUCTION_RECONSTRUCTIONPLANNER_H
#define CADCAPTURE_RECONSTRUCTION_RECONSTRUCTIONPLANNER_H

#include "model/ReconstructionPackage.h"

namespace cadcapture {

class ReconstructionPlanner
{
public:
  bool Plan(ReconstructionPackage& package);
};

}

#endif
