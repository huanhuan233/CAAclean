# CATIA V5R21 CAA batch executable.
BUILT_OBJECT_TYPE=LOAD MODULE

OS = COMMON

LOCAL_CCFLAGS = /EHsc

LINK_WITH = \
  JS0GROUP \
  CATObjectModelerBase \
  CATObjectSpecsModeler \
  CATMecModInterfaces \
  CATMathematics \
  CATGMModelInterfaces \
  CATTPSItf \
  CATTPSUUID \
  KnowledgeItf \
  CATPartInterfaces \
  PartInterfacesUUID
