export function nativeAssetLoadPolicy(input: {
  loadedNativeTreeFromApi: boolean;
  sourceFormat: string;
  status: string;
}) {
  return {
    loadProductOccurrencesJsonl:
      input.sourceFormat === 'CATPRODUCT' && !input.loadedNativeTreeFromApi,
    loadFeaturesJsonl:
      input.sourceFormat !== 'CATPRODUCT' && !input.loadedNativeTreeFromApi,
    // 原生参数和属性按选中节点从 PostgreSQL API 读取，禁止首屏下载整包 JSONL。
    loadParametersJsonl: false,
    loadPropertyFactsJsonl: false,
    // 处理中资产端点会返回 409；CATProduct 重资产继续按首屏内存策略禁用。
    loadHeavySemanticsJsonl: input.status === 'ready' && input.sourceFormat !== 'CATPRODUCT'
  };
}
