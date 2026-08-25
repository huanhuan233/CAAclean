BUILT_OBJECT_TYPE=LOAD MODULE

OS = COMMON

LOCAL_CCFLAGS = /EHsc /I"src"

LINK_WITH = \
  JS0GROUP \
  CATObjectModelerBase \
  CATObjectSpecsModeler \
  CATMecModInterfaces
