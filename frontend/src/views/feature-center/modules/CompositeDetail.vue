<script setup lang="ts">
import { computed } from 'vue';
import { ElMessage } from 'element-plus';
import type { CompositeCoverageRecord, CompositeStructureRecord } from '@/service/api/cad';
import StackDetail from './StackDetail.vue';
import PlyGroupDetail from './PlyGroupDetail.vue';
import SequenceDetail from './SequenceDetail.vue';
import PlyDetail from './PlyDetail.vue';
import { compositeDetailKind, compositeTitle, compositeType, orderStatus, updateStatus } from './composite-view-model';
import './composite-panels.css';

const props = defineProps<{
  record: CompositeStructureRecord | null; relatedRecords: CompositeStructureRecord[];
  loading: boolean; error: string;
  coverage: CompositeCoverageRecord | null; coverageLoading: boolean;
  coverageError: string; coverageComputing: boolean; selectedRegionId: string;
}>();
const emit = defineEmits<{
  recompute: [basis: 'cured' | 'uncured']; selectRegion: [regionId: string]; selectMember: [objectId: string];
}>();
const kind = computed(() => props.record ? compositeDetailKind(props.record) : 'other');
const status = computed(() => updateStatus(props.record?.update_status || ''));

async function copyId() {
  if (!props.record) return;
  try {
    await navigator.clipboard.writeText(props.record.object_id);
    ElMessage.success('对象 ID 已复制');
  } catch {
    ElMessage.error('复制失败，请从来源与诊断中选择 ID');
  }
}
</script>

<template>
  <div class="composite-detail">
    <template v-if="record">
      <header class="composite-header">
        <span class="composite-type-icon"><SvgIcon :icon="compositeType(record.kind).icon" /></span>
        <div class="composite-header-main">
          <h3 :title="compositeTitle(record)">{{ compositeTitle(record) }}</h3>
          <div class="composite-id-line"><span :title="record.object_id">ID：{{ record.object_id }}</span>
            <button type="button" class="composite-icon-action" aria-label="复制对象 ID" @click="copyId">
              <SvgIcon icon="mdi:content-copy" /></button></div>
          <span class="composite-status" :class="status.tone" :title="record.update_status">{{ status.text }}</span>
        </div>
      </header>
      <StackDetail v-if="kind === 'stacking'" :record="record" :related-records="relatedRecords"
        @select-member="emit('selectMember', $event)" />
      <PlyGroupDetail v-else-if="kind === 'group'" :record="record" :related-records="relatedRecords"
        :coverage="coverage" :coverage-loading="coverageLoading" :coverage-error="coverageError"
        :coverage-computing="coverageComputing" :selected-region-id="selectedRegionId"
        @select-member="emit('selectMember', $event)" @recompute="emit('recompute', $event)"
        @select-region="emit('selectRegion', $event)" />
      <SequenceDetail v-else-if="kind === 'sequence'" :record="record" :related-records="relatedRecords"
        @select-member="emit('selectMember', $event)" />
      <PlyDetail v-else-if="kind === 'ply'" :record="record" :related-records="relatedRecords"
        @select-member="emit('selectMember', $event)" />
      <section v-else class="composite-panel"><h4>{{ compositeType(record.kind).label }}</h4>
        <p class="composite-muted">此对象类型暂无专用详情；原始证据保留在下方诊断中。</p></section>
      <details class="composite-diagnostics"><summary>来源与诊断</summary>
        <p>原始类型：{{ record.kind }}；原始更新状态：{{ record.update_status }}；层序状态：{{ orderStatus(record.order_status) }}</p>
        <p>文档：{{ record.document_id }}；对象 ID：{{ record.object_id }}；树出现 {{ record.occurrence_ids.length }} 处</p>
        <p v-for="path in record.occurrence_paths" :key="path">{{ path }}</p>
        <p v-for="(field, key) in record.fields" :key="key" :title="field.source_api">
          {{ key }}：{{ String(field.raw_value ?? '') }} {{ field.raw_unit }}（{{ field.read_status }}）</p>
        <p v-for="diagnostic in record.diagnostics" :key="diagnostic">{{ diagnostic }}</p>
      </details>
    </template>
    <p v-else-if="loading" class="composite-muted">正在读取复材对象详情…</p>
    <p v-else-if="error" class="composite-muted">{{ error }}</p>
    <p v-else class="composite-muted">请选择复材对象。</p>
  </div>
</template>
