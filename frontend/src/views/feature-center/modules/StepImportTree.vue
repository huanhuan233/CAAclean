<script setup lang="ts">
import { computed, ref } from 'vue';
import { useElementSize } from '@vueuse/core';
import { filterStepImportTree } from './step-import-tree';
import type { StepImportNode } from './step-import-tree';

defineOptions({ name: 'StepImportTree' });

const props = defineProps<{
  nodes: StepImportNode[];
  selectedId: string;
  loading: boolean;
  error: string;
}>();
const emit = defineEmits<{ select: [node: StepImportNode]; retry: [] }>();
const query = ref('');
const scrollRef = ref<HTMLElement | null>(null);
const { height } = useElementSize(scrollRef);
const filteredNodes = computed(() => filterStepImportTree(props.nodes, query.value));
const expandedKeys = computed(() => query.value.trim()
  ? collectParents(filteredNodes.value) : props.nodes.map(node => node.id));

function collectParents(nodes: StepImportNode[]): string[] {
  return nodes.flatMap(node => node.children.length ? [node.id, ...collectParents(node.children)] : []);
}

function iconFor(node: StepImportNode) {
  return {
    root: 'lucide:file-box', imported_object: 'lucide:box',
    body: 'lucide:package-open', solid: 'lucide:box-3d'
  }[node.entityType] || 'lucide:component';
}
</script>

<template>
  <section class="step-import-browser">
    <div class="step-import-toolbar">
      <ElInput v-model="query" clearable size="small" placeholder="搜索导入对象名称或 ID">
        <template #prefix><SvgIcon icon="lucide:search" /></template>
      </ElInput>
    </div>
    <p class="step-import-notice">STEP 导入结构仅表示文件中的对象分组，不代表 CATIA 原生建模历史。</p>
    <div ref="scrollRef" class="step-import-scroll">
      <ElTreeV2 v-if="filteredNodes.length" :data="filteredNodes"
        :props="{ value: 'id', label: 'label', children: 'children' }"
        :height="Math.max(100, height - 4)" :item-size="36" :indent="18"
        :default-expanded-keys="expandedKeys" :current-node-key="selectedId"
        highlight-current @node-click="emit('select', $event as StepImportNode)">
        <template #default="{ data }">
          <span class="step-import-row" :title="`${data.label} · ${data.id}`">
            <SvgIcon :icon="iconFor(data)" class="step-import-icon" />
            <span class="step-import-title">{{ data.label }}</span>
          </span>
        </template>
      </ElTreeV2>
      <div v-else-if="loading" class="step-import-state">正在读取 STEP 导入结构…</div>
      <div v-else-if="error" class="step-import-state">
        <span>{{ error }}</span>
        <ElButton text type="primary" @click="emit('retry')">重试</ElButton>
      </div>
      <ElEmpty v-else :description="query ? '没有匹配的导入对象' : '当前 STEP 没有已入库的导入结构'" />
    </div>
  </section>
</template>

<style scoped>
.step-import-browser { display: flex; flex: 1; flex-direction: column; min-height: 0; }
.step-import-toolbar { padding: 9px 10px 5px; flex: none; }
.step-import-notice { flex: none; margin: 0; padding: 4px 12px 8px; color: var(--el-text-color-secondary); font-size: 11px; line-height: 1.5; }
.step-import-scroll { flex: 1; min-height: 0; overflow: hidden; }
.step-import-row { display: flex; align-items: center; min-width: 0; width: 100%; gap: 7px; font-size: 13px; }
.step-import-icon { flex: none; color: var(--el-text-color-secondary); }
.step-import-title { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.step-import-state { display: flex; align-items: center; justify-content: center; flex-wrap: wrap; min-height: 120px; gap: 8px; padding: 16px; color: var(--el-text-color-secondary); font-size: 12px; text-align: center; }
</style>
