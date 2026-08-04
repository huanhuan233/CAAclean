# Decoder 扩展指南

## 通用 Capability 与 Payload

新增原生 Decoder 时，不要修改 Crawler 或给 `INativeObjectView` 增加专用 Getter。应实现一个继承 `INativeCapabilityView` 的强类型视图，并由 CAA Adapter 通过稳定 Capability ID 返回。Core Decoder 只调用 `FindCapability`，不能引用 CATIA 头文件。

每类 Decoder 应提供继承 `ITypedPayload` 的独立强类型数据，完整实现 Type ID、Clone 和自身 JSON 写出。`FeatureRecord` 负责 Payload 生命周期；中央 JSON Writer 无需新增类型判断。一个对象最多正式接管一个 Typed Payload，同优先级多 Decoder 成功会产生冲突诊断。

返回 NotMatched 或 Unsupported 时 Registry 继续；Exception/Rejected/Partial 是否继续由 `ContinueTypedAfterFailure` 决定。任何失败路径都不能污染 Generic/Opaque 回退记录。

新增原生特征 Decoder 时实现 `INativeFeatureDecoder`（通用 Decoder 仍可实现 `IFeatureDecoder`）：稳定 ASCII ID、显式 priority、无副作用候选 Match 和对象级 Decode。Decoder 不能全局遍历、保留 CAA 指针或自行修改对象枚举守恒计数。

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

`NativeHoleDecoder` 是当前唯一注册的 Part Design 专用 Decoder。未来 Pad/Pocket/Fillet/Chamfer/Pattern 必须各自增加 API 无关 View、独立 Typed Payload、真实 R21 专用接口适配器和编译期注册；Crawler 无需修改。StartUp 只能预筛选，接口确认失败后按统一策略直接 Generic，不尝试靠名称补救。同一对象有多个候选时 Registry 输出冲突诊断并由 priority + 稳定 ID 决胜。
