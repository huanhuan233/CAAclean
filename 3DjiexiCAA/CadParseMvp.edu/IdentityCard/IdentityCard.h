// 本文件是 CAA Framework 的 IdentityCard，不会作为普通 C++ 运行时代码执行。
// AddPrereqComponent 用途：声明编译和链接 CadParseMvp 所需的 R21 Framework 依赖。
// Public 表示这里只使用对应 Framework 对外公开的接口契约。
AddPrereqComponent("System", Public);
AddPrereqComponent("ObjectModelerBase", Public);
AddPrereqComponent("ObjectSpecsModeler", Public);
AddPrereqComponent("MecModInterfaces", Public);
// 用途：提供 Public CATMathPoint/CATMathVector 等数学对象，用于拓扑中心点和三角化结果读取。
AddPrereqComponent("Mathematics", Public);
// 用途：提供 Public CATBody/CATTopology/CATCell，用于读取最终实体的真实 Face/Edge/Vertex 拓扑摘要。
AddPrereqComponent("GMModelInterfaces", Public);
// 用途：提供 Public CATITPSDocument/CATITPSSet，用于读取 FTA/TPS 集合级摘要。
AddPrereqComponent("CATTPSInterfaces", Public);
// 用途：提供 Public CATICkeParm/CATICkeType/CATICkeInst 的类型化 String 参数读取契约。
AddPrereqComponent("KnowledgeInterfaces", Public);
// 用途：提供 Public CATIAHole/CATIALimit、真实枚举和对应 Automation C++ 接口。
AddPrereqComponent("PartInterfaces", Public);

// Purpose: expose Public CATIProduct for CATProduct reference/instance hierarchy extraction.
AddPrereqComponent("ProductStructure", Public);
AddPrereqComponent("ProductStructureInterfaces", Public);
