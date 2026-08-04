import assert from 'node:assert/strict';
import test from 'node:test';
import {
  readRecentFeatureCenterBuildId,
  resolveFeatureCenterBuildId,
  saveRecentFeatureCenterBuildId
} from '../modules/recent-result';

class MemoryStorage {
  private readonly values = new Map<string, string>();

  getItem(key: string) { return this.values.get(key) ?? null; }
  setItem(key: string, value: string) { this.values.set(key, value); }
}

test('只恢复上一次真实成功加载的 build id', () => {
  const storage = new MemoryStorage();
  assert.equal(readRecentFeatureCenterBuildId(storage), '');

  saveRecentFeatureCenterBuildId(storage, ' build-123 ');
  assert.equal(readRecentFeatureCenterBuildId(storage), 'build-123');
});

test('空 build id 不会覆盖已有结果', () => {
  const storage = new MemoryStorage();
  saveRecentFeatureCenterBuildId(storage, 'build-123');
  saveRecentFeatureCenterBuildId(storage, '   ');
  assert.equal(readRecentFeatureCenterBuildId(storage), 'build-123');
});

test('路由指定真实结果时优先使用路由编号', () => {
  assert.equal(resolveFeatureCenterBuildId('route-build', 'recent-build'), 'route-build');
});

test('路由没有编号时只恢复最近真实结果', () => {
  assert.equal(resolveFeatureCenterBuildId('', 'recent-build'), 'recent-build');
  assert.equal(resolveFeatureCenterBuildId('', ''), '');
});
