# Decoder 扩展指南

新增 Decoder 时实现 `IFeatureDecoder`：稳定 ASCII ID、显式 priority、无副作用 `Match` 和对象级 `Decode`。Decoder 不能全局遍历、保留 CAA 指针或自行修改枚举守恒计数。

匹配证据优先级是：经注册验证的接口、StartUp/Late Type、SuperType、已验证 native type、容器/Family，显示名只能作为低可信最后依据。同 priority 时稳定 Decoder ID 决胜并输出 warning，结果不依赖注册顺序。

CAA 读取应放在 Native View/Adapter 后面；API 无关 Decoder 只看契约。例如新参数类型应扩展参数视图和 `ParameterValueData`，明确区分 `typed_caa_value`、`display_representation`、`parsed_from_display`、`unavailable`。接口不支持是正常结果，异常才计入 exception。

注册步骤：

1. 在本机 R21 PublicInterfaces/Encyclopedia/.edu 确认接口、头文件和模块。
2. 在 IdentityCard/Imakefile 增加真实依赖。
3. 编写失败的 Fake View 测试和 Golden Case。
4. 实现 Adapter、Decoder，并在 `RegisterCoreDecoders` 的编译期工厂创建。
5. 通过 `JsonArtifactWriter` 增加通用字段；不要在 Decoder 手拼 JSON。
6. 运行 VS2008 测试、CAA 构建和合法 CATPart Smoke Test。
7. 将证据和实际状态写入 `CAA_R21_API_EVIDENCE.md`。

若接口不能确认，添加 `TODO(R21_API_VERIFY)` 并保持 Generic/Opaque 可用。专用 Decoder 失败或抛异常只能影响当前对象；Registry 必须继续 Generic，必要时 Opaque。增加 Golden Case 时同时验证 ID 来源完整性、核心 JSONL 双跑稳定性和三套守恒关系。

未来原生 Pad/Pocket/Hole Decoder 必须用对应 R21 原生接口确认对象语义；不能复用当前 GSMTool 名称规则冒充原生 Part Design 识别。
