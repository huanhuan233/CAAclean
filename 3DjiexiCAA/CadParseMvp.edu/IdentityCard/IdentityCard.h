// 本文件是 CAA Framework 的 IdentityCard，不会作为普通 C++ 运行时代码执行。
// AddPrereqComponent 用途：声明编译和链接 CadParseMvp 所需的 R21 Framework 依赖。
// Public 表示这里只使用对应 Framework 对外公开的接口契约。
AddPrereqComponent("System", Public);
AddPrereqComponent("ObjectModelerBase", Public);
AddPrereqComponent("ObjectSpecsModeler", Public);
AddPrereqComponent("MecModInterfaces", Public);
