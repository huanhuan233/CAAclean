<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import { fetchCompositeStructure } from '@/service/api/cad';
import type { CompositeStructureRecord } from '@/service/api/cad';

const props = defineProps<{ buildId: string; selectedId: string }>();
const emit = defineEmits<{ select: [record: CompositeStructureRecord]; availability: [available: boolean] }>();
const records = ref<CompositeStructureRecord[]>([]);
const total = ref(0);
const loading = ref(false);
const error = ref('');
const query = ref('');
let generation = 0;
let controller: AbortController | null = null;
const kindNames: Record<CompositeStructureRecord['kind'], string> = {
  stacking: '叠层', group: '铺层组', sequence: '序列', ply: '单层', cut_piece: '子片', cut_piece_group: '子片组'
};
const visible = computed(() => records.value.filter(row =>
  `${row.display_name || ''} ${row.object_id} ${kindNames[row.kind] || row.kind}`.toLowerCase().includes(query.value.trim().toLowerCase())));

async function load(reset = false) {
  if (!props.buildId || loading.value) return;
  if (reset) { records.value = []; total.value = 0; }
  loading.value = true; error.value = '';
  const token = generation;
  const response = await fetchCompositeStructure(props.buildId, records.value.length, 100,
    { signal: controller?.signal, silent: true });
  if (token !== generation) return;
  loading.value = false;
  if (response.error || !response.data) {
    error.value = '复材结构未采集、尚未入库或读取失败。';
    emit('availability', false);
    return;
  }
  records.value = [...records.value, ...response.data.records];
  total.value = response.data.total;
  emit('availability', total.value > 0);
}

watch(() => props.buildId, () => {
  controller?.abort(); controller = new AbortController(); generation += 1;
  records.value = []; total.value = 0; error.value = ''; loading.value = false; query.value = '';
  emit('availability', false);
  if (props.buildId) void load();
}, { immediate: true });
onBeforeUnmount(() => controller?.abort());

function label(row: CompositeStructureRecord): string {
  return `${kindNames[row.kind] || '复材对象'} · ${row.display_name || row.object_id}`;
}
</script>

<template>
  <div class="composite-explorer">
    <div class="composite-search"><ElInput v-model="query" clearable placeholder="搜索铺层名称或 ID" aria-label="搜索铺层名称或 ID" /></div>
    <div class="composite-list">
      <button v-for="row in visible" :key="`${row.document_id}:${row.object_id}`" type="button"
        class="composite-row" :class="{ selected: selectedId === row.object_id }" @click="emit('select', row)">
        <strong :title="label(row)">{{ label(row) }}</strong>
        <span>{{ row.kind === 'ply' ? (row.fields.composite_orientation?.raw_display_text || '方向未取得') :
          row.order_status === 'native_complete' ? '原生顺序已读取' : '层序未完整确认' }}</span>
        <small :title="row.object_id">ID：{{ row.object_id }}</small>
      </button>
      <p v-if="error" class="composite-empty">{{ error }} <button type="button" @click="load(true)">重试</button></p>
      <p v-else-if="!loading && !records.length" class="composite-empty">当前结果没有复材铺层结构</p>
      <p v-else-if="!loading && !visible.length" class="composite-empty">已加载结果中没有匹配对象</p>
    </div>
    <div class="composite-footer">
      <span>已加载 {{ records.length }} / {{ total }} 个对象{{ query ? ' · 仅搜索已加载结果' : '' }}</span>
      <button v-if="records.length < total" type="button" :disabled="loading" @click="load()">继续加载</button>
      <span v-else-if="loading">读取中…</span>
    </div>
  </div>
</template>

<style scoped>
.composite-explorer { display: flex; flex-direction: column; min-height: 0; height: 100%; }
.composite-search { flex: none; padding: 8px 10px; }
.composite-list { flex: 1; min-height: 0; overflow-y: auto; }
.composite-row { display: flex; flex-direction: column; width: 100%; min-width: 0; text-align: left;
  padding: 8px 12px; border: 0; border-bottom: 1px solid var(--el-border-color-extra-light);
  background: transparent; color: var(--el-text-color-primary); cursor: pointer; }
.composite-row:hover { background: var(--el-fill-color-light); }
.composite-row.selected { background: var(--el-color-primary-light-9); color: var(--el-color-primary); }
.composite-row strong { font-size: 13px; font-weight: 600; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.composite-row span, .composite-row small { font-size: 11px; color: var(--el-text-color-secondary); }
.composite-empty { padding: 16px 12px; color: var(--el-text-color-secondary); }
.composite-footer { display: flex; justify-content: space-between; gap: 8px; flex: none; padding: 8px 10px;
  border-top: 1px solid var(--el-border-color-light); font-size: 11px; color: var(--el-text-color-secondary); }
</style>
