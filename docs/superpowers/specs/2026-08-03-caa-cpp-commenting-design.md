# CAA C++ 教学注释设计

## 目标

为 `3DjiexiCAA` 下全部 `.cpp` 和 `.h` 文件增加中文教学注释，帮助长期未使用 C++ 的维护者重新理解 C++03、STL、CAA 对象生命周期以及本项目解析流程。此次工作只补充注释，不改变程序行为、公开接口、构建配置或输出格式。

## 覆盖范围

- `CadParseContracts.h`：纯数据契约、抽象接口、Decoder 注册与解析上下文。
- `CadParseCore.cpp`：Registry、Generic/Opaque 兜底、Crawler 和统计逻辑。
- `CadParseIR.h/.cpp`：JSON、JSONL、Manifest、诊断和覆盖率输出。
- `CadParseCAA.h/.cpp`：CATIA Session、Document、Native Object Adapter 和遍历入口。
- `CadParseBatch.cpp`：命令行参数、运行阶段、错误码和资源清理。
- `CadParseSelfTests.cpp` 与 `tests/CadParseCoreTestMain.cpp`：无许可证测试及测试入口。
- `IdentityCard.h`：CAA Framework 依赖声明。

## 注释层级

1. 每个文件开头说明该文件在解析链路中的职责及主要依赖。
2. 每个类、结构体和接口前说明它代表什么、由谁创建、由谁使用。
3. 每个函数声明或定义前必须说明函数用途。
4. 重要函数另外说明参数、返回值、副作用、对象所有权、失败路径和兜底行为。
5. 复杂代码块旁解释“为什么这样写”，包括 C++03 限制、STL 迭代器、虚函数分派、RAII、CAA `AddRef/Release`、稳定排序和异常隔离。
6. 简单赋值和语义明显的语句不逐行复述，避免注释遮蔽真实控制流。

## 注释格式

- 使用中文，保留可检索的 C++、STL、CAA、RAII、Decoder、Generic、Opaque 等英文术语。
- 函数采用函数前置 `//` 注释；复杂函数可使用连续多行说明。
- 头文件声明处说明外部契约，源文件定义处说明实现策略。两处信息互补，不机械重复。
- 对 CAA 指针明确区分借用引用、持有引用以及需要 `Release` 的所有权。
- 不把未经本机 R21 资料验证的行为写成确定事实。

## 质量约束与验证

- 不修改函数签名、类布局、条件判断、循环、字符串常量或输出 Schema。
- 不引入 C++11 及以后语法。
- 使用 `git diff --word-diff` 和普通 diff 检查实际变更仅为注释与必要空行。
- 运行现有无许可证测试。
- 在本机 CAA 环境可用时运行现有构建；若环境或许可证阻止验证，准确记录未执行项。
- 重点抽查 Session/Document 清理、Decoder 失败兜底和 Coverage 守恒相关代码，确保注释与实现一致。

## 完成标准

- 范围内每个函数前都有用途说明。
- 核心数据结构、接口、生命周期和主解析链路能够仅借助源码注释理解。
- 测试结果与注释前一致。
- Git diff 中没有由本轮引入的行为变化。
