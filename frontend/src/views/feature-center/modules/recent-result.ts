const RECENT_FEATURE_CENTER_BUILD_KEY = 'feature-center:last-successful-catpart-build';

interface StorageReader {
  getItem(key: string): string | null;
}

interface StorageWriter extends StorageReader {
  setItem(key: string, value: string): void;
}

// 用途：读取上一次真实成功加载的 CATPart 构建编号；不存在时返回空值而不是伪造格式或模型。
export function readRecentFeatureCenterBuildId(storage: StorageReader) {
  return (storage.getItem(RECENT_FEATURE_CENTER_BUILD_KEY) || '').trim();
}

// 用途：仅在构建编号有效时更新最近结果，空值不能覆盖已有的真实记录。
export function saveRecentFeatureCenterBuildId(storage: StorageWriter, buildId: string) {
  const normalized = buildId.trim();
  if (normalized) storage.setItem(RECENT_FEATURE_CENTER_BUILD_KEY, normalized);
}

// 用途：优先采用当前路由明确指定的结果，否则才恢复上一次成功加载的真实 CATPart 结果。
export function resolveFeatureCenterBuildId(requestedBuildId: string, recentBuildId: string) {
  return requestedBuildId.trim() || recentBuildId.trim();
}
