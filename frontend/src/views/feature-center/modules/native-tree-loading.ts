import { isSystemNativeFeatureRecord } from './native-feature-tree';
import type { NativeFeatureRecord } from './native-feature-tree';

export interface NativeChildPage {
  records: NativeFeatureRecord[];
  nextOffset: number | null;
}

// Yield each database page immediately; only walk hidden containers with children.
export async function* nativeChildPages(
  parentId: string,
  fetchPage: (parentId: string, offset: number) => Promise<NativeChildPage>
): AsyncGenerator<NativeFeatureRecord[]> {
  const queue = [{ parentId, offset: 0 }];
  const visited = new Set<string>();
  while (queue.length) {
    const request = queue.shift()!;
    const key = `${request.parentId}:${request.offset}`;
    if (visited.has(key)) continue;
    visited.add(key);
    const page = await fetchPage(request.parentId, request.offset);
    yield page.records;
    for (const record of page.records) {
      const attrs = record.attributes || {};
      if (isSystemNativeFeatureRecord(record) && (attrs.has_children || Number(attrs.child_count || 0) > 0)) {
        queue.push({ parentId: record.feature_id, offset: 0 });
      }
    }
    if (page.nextOffset !== null) {
      if (page.nextOffset <= request.offset) throw new Error('树分页游标没有前进');
      queue.push({ parentId: request.parentId, offset: page.nextOffset });
    }
  }
}
