<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import { fetchComponentBuildMbdAnnotations, fetchComponentBuildNativeEvidence } from '@/service/api';
import type { MbdAnnotationRecord, MbdNodeRecord } from '@/service/api/cad';
import { mbdAnnotationTitle, mbdNodeTitle, mbdReadStatus, mbdTypeName } from './mbd-view-model';

const props = defineProps<{ buildId: string; revisionId: string; selectedId: string }>();
const emit = defineEmits<{
  selectAnnotation: [record: MbdAnnotationRecord];
  selectNode: [record: MbdNodeRecord];
}>();

const mode = ref<'annotations' | 'hierarchy'>('annotations');
const annotations = ref<MbdAnnotationRecord[]>([]);
const nodes = ref<MbdNodeRecord[]>([]);
const total = ref(0);
const nodeTotal = ref(0);
const nextOffset = ref<number | null>(0);
const nodeNextOffset = ref<number | null>(0);
const loading = ref(false);
const error = ref('');
const keyword = ref('');
const kind = ref('');
const setId = ref('');
const viewId = ref('');
const readStatus = ref('');
let generation = 0;
let controller: AbortController | null = null;
let searchTimer: ReturnType<typeof setTimeout> | null = null;

const kinds = [
  ['', '全部类型'], ['dimension', '尺寸'], ['gdt', '形位公差'],
  ['gdt_nonsemantic', '非语义公差'], ['roughness', '粗糙度'],
  ['datum', '基准'], ['datum_simple', '普通基准'], ['datum_system', '基准体系'],
  ['text', '文本'], ['flag_note', '旗标'], ['noa', 'NOA']
] as const;
const loadedSets = computed(() => nodes.value.filter(node => node.pmi_kind === 'fta_set'));
const visibleNodes = computed(() => nodes.value.filter(node =>
  ['fta_set', 'fta_view', 'fta_capture'].includes(node.pmi_kind)
));

async function loadAnnotations(reset = false) {
  if (!props.buildId || !props.revisionId || loading.value) return;
  if (reset) {
    generation += 1;
    controller?.abort();
    controller = new AbortController();
    annotations.value = [];
    nextOffset.value = 0;
  }
  if (nextOffset.value === null) return;
  const ownGeneration = generation;
  loading.value = true;
  error.value = '';
  const response = await fetchComponentBuildMbdAnnotations(props.buildId, {
    offset: nextOffset.value, page_size: 100,
    annotation_kind: kind.value || undefined,
    set_id: setId.value || undefined,
    view_id: viewId.value.trim() || undefined,
    read_status: readStatus.value || undefined,
    search: keyword.value.trim() || undefined
  }, { signal: controller?.signal, silent: true });
  if (ownGeneration !== generation) return;
  loading.value = false;
  if (response.error || !response.data) {
    error.value = '标注数据库读取失败，请重试。';
    return;
  }
  annotations.value = [...annotations.value, ...response.data.records];
  total.value = response.data.total;
  nextOffset.value = response.data.next_offset;
}

async function loadNodes(reset = false) {
  if (!props.buildId || !props.revisionId || loading.value) return;
  if (reset) {
    generation += 1;
    controller?.abort();
    controller = new AbortController();
    nodes.value = [];
    nodeNextOffset.value = 0;
  }
  if (nodeNextOffset.value === null) return;
  const ownGeneration = generation;
  loading.value = true;
  error.value = '';
  const response = await fetchComponentBuildNativeEvidence<MbdNodeRecord>(
    props.buildId, 'pmi_entities', nodeNextOffset.value, 100, { signal: controller?.signal, silent: true }
  );
  if (ownGeneration !== generation) return;
  loading.value = false;
  if (response.error || !response.data) {
    error.value = '标注层级未入库或读取失败，请重试。';
    return;
  }
  nodes.value = [...nodes.value, ...response.data.records];
  nodeTotal.value = response.data.total;
  nodeNextOffset.value = response.data.next_offset;
}

function refresh() {
  loading.value = false;
  if (mode.value === 'annotations') void loadAnnotations(true);
  else void loadNodes(true);
}

watch(() => [props.buildId, props.revisionId], () => {
  generation += 1;
  controller?.abort();
  annotations.value = [];
  nodes.value = [];
  nextOffset.value = 0;
  nodeNextOffset.value = 0;
  total.value = 0;
  nodeTotal.value = 0;
  error.value = '';
  if (props.buildId && props.revisionId) refresh();
}, { immediate: true });
watch(mode, refresh);
watch([kind, setId, readStatus], refresh);
watch([keyword, viewId], () => {
  if (searchTimer) clearTimeout(searchTimer);
  searchTimer = setTimeout(refresh, 300);
});
onBeforeUnmount(() => {
  generation += 1;
  controller?.abort();
  if (searchTimer) clearTimeout(searchTimer);
});
</script>

<template>
  <section class="mbd-explorer" aria-label="MBD 标注浏览器">
    <div class="mbd-controls">
      <div class="mbd-mode">
        <button type="button" :class="{ active: mode === 'annotations' }" @click="mode = 'annotations'">标注</button>
        <button type="button" :class="{ active: mode === 'hierarchy' }" @click="mode = 'hierarchy'">集合与视图</button>
      </div>
      <template v-if="mode === 'annotations'">
        <ElInput v-model="keyword" clearable placeholder="搜索标注名称、正文或 ID" aria-label="搜索 MBD 标注" />
        <div class="mbd-filters">
          <ElSelect v-model="kind" aria-label="标注类型" placeholder="全部类型">
            <ElOption v-for="option in kinds" :key="option[0]" :value="option[0]" :label="option[1]" />
          </ElSelect>
          <ElSelect v-model="setId" clearable aria-label="所属标注集" placeholder="全部标注集">
            <ElOption value="" label="全部标注集" />
            <ElOption v-for="node in loadedSets" :key="node.pmi_id" :value="node.pmi_id" :label="mbdNodeTitle(node)" />
          </ElSelect>
        </div>
        <div class="mbd-filters">
          <ElInput v-model="viewId" clearable placeholder="视图/捕获 ID" aria-label="视图或捕获 ID 筛选" />
          <ElSelect v-model="readStatus" aria-label="读取状态" placeholder="全部状态">
            <ElOption value="" label="全部状态" />
            <ElOption value="available" label="已读取" />
            <ElOption value="partial" label="部分读取" />
            <ElOption value="interface_only" label="仅接口可用" />
            <ElOption value="empty" label="原生空值" />
            <ElOption value="unavailable" label="不可读取" />
            <ElOption value="unsupported" label="接口不支持" />
            <ElOption value="failed" label="读取失败" />
          </ElSelect>
        </div>
        <small v-if="nodeNextOffset !== null">标注集筛选仅列出已加载集合；可在“集合与视图”继续加载。</small>
      </template>
    </div>
    <div class="mbd-list" role="list">
      <template v-if="mode === 'annotations'">
        <button v-for="record in annotations" :key="`${revisionId}:${record.fta_semantic_id}`" type="button"
          class="mbd-row" :class="{ selected: selectedId === record.fta_semantic_id, uncertain: mbdReadStatus(record.read_status).tone !== 'success' }"
          :title="mbdAnnotationTitle(record)" @click="emit('selectAnnotation', record)">
          <span class="mbd-row-head"><strong>{{ mbdAnnotationTitle(record) }}</strong>
            <ElTag size="small" :type="mbdReadStatus(record.read_status).tone">{{ mbdReadStatus(record.read_status).label }}</ElTag>
          </span>
          <small>{{ mbdTypeName(record.component_kind) }} · {{ record.fta_set_id }}</small>
          <small class="mbd-id">{{ record.fta_semantic_id }}</small>
        </button>
      </template>
      <template v-else>
        <button v-for="node in visibleNodes" :key="`${revisionId}:${node.pmi_id}`" type="button"
          class="mbd-row" :class="{ selected: selectedId === node.pmi_id, uncertain: mbdReadStatus(node.read_status).tone !== 'success' }"
          :title="mbdNodeTitle(node)" @click="emit('selectNode', node)">
          <span class="mbd-row-head"><strong>{{ mbdNodeTitle(node) }}</strong>
            <ElTag size="small" :type="mbdReadStatus(node.read_status).tone">{{ mbdReadStatus(node.read_status).label }}</ElTag>
          </span>
          <small>{{ node.pmi_kind === 'fta_set' ? '标注集' : node.pmi_kind === 'fta_view' ? '视图' : '捕获' }} · {{ node.owning_document_id || '归属未解析' }}</small>
          <small class="mbd-id">{{ node.pmi_id }}</small>
        </button>
      </template>
      <div v-if="loading" class="mbd-state">正在读取数据库…</div>
      <div v-else-if="error" class="mbd-state">{{ error }} <ElButton size="small" @click="refresh">重试</ElButton></div>
      <div v-else-if="mode === 'annotations' && !annotations.length" class="mbd-state">当前筛选没有标注，或原生集合为空。</div>
      <div v-else-if="mode === 'hierarchy' && !visibleNodes.length" class="mbd-state">尚无已入库的标注集合或视图。</div>
      <ElButton v-if="!loading && (mode === 'annotations' ? nextOffset !== null : nodeNextOffset !== null)"
        class="mbd-more" text @click="mode === 'annotations' ? loadAnnotations() : loadNodes()">继续加载</ElButton>
    </div>
    <footer class="mbd-footer">{{ mode === 'annotations' ? `共 ${total} 条标注，已加载 ${annotations.length}` : `已加载 ${nodes.length}/${nodeTotal} 个层级对象` }}</footer>
  </section>
</template>

<style scoped>
.mbd-explorer { display: flex; flex-direction: column; height: 100%; min-height: 0; min-width: 0; }
.mbd-controls { flex: none; display: grid; gap: 8px; padding: 10px; }
.mbd-mode { display: flex; padding: 3px; border-radius: 8px; background: var(--el-fill-color-light); }
.mbd-mode button { flex: 1; min-width: 0; padding: 6px 3px; border-radius: 6px; color: var(--el-text-color-regular); }
.mbd-mode button.active { color: var(--el-color-primary); background: var(--el-color-primary-light-9); }
.mbd-filters { display: flex; gap: 6px; min-width: 0; }
.mbd-filters :deep(.el-select) { width: 50%; min-width: 0; }
.mbd-controls small { color: var(--el-text-color-secondary); }
.mbd-list { flex: 1; min-height: 0; overflow-y: auto; padding: 2px 10px 10px; }
.mbd-row { display: block; width: 100%; min-width: 0; margin: 0 0 7px; padding: 10px; text-align: left; border: 1px solid var(--el-border-color-light); border-radius: 7px; background: var(--el-bg-color); color: var(--el-text-color-primary); }
.mbd-row:hover, .mbd-row:focus-visible { background: var(--el-fill-color-light); }
.mbd-row.selected { border-color: var(--el-color-primary); background: var(--el-color-primary-light-9); color: var(--el-color-primary); }
.mbd-row.selected.uncertain { border-color: var(--el-color-warning); background: var(--el-color-warning-light-9); color: var(--el-color-warning); }
.mbd-row-head { display: flex; align-items: center; gap: 6px; min-width: 0; }
.mbd-row-head strong { flex: 1; min-width: 0; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; font-size: 13px; }
.mbd-row small { display: block; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; color: var(--el-text-color-secondary); font-size: 11px; line-height: 18px; }
.mbd-id { font-family: ui-monospace, SFMono-Regular, Consolas, monospace; }
.mbd-state { padding: 20px 8px; color: var(--el-text-color-secondary); text-align: center; }
.mbd-more { width: 100%; }
.mbd-footer { flex: none; padding: 9px 11px; border-top: 1px solid var(--el-border-color-light); color: var(--el-text-color-secondary); font-size: 12px; }
</style>
