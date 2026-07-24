<script setup lang="ts">
import { computed } from 'vue';
import { clamp01 } from '../geometry';
import type { AnnotationPointKey, PatentAnnotation, Point2D } from '../types';

defineOptions({ name: 'PatentAnnotationInspector' });

const props = withDefaults(
  defineProps<{
    annotations?: PatentAnnotation[];
    selectedAnnotation: PatentAnnotation | null;
  }>(),
  {
    annotations: () => []
  }
);

const emit = defineEmits<{
  (event: 'select', annotationId: string): void;
  (event: 'update', annotationId: string, patch: Partial<PatentAnnotation>): void;
  (event: 'delete', annotationId: string): void;
}>();

const selectedBboxText = computed(() => {
  const bbox = props.selectedAnnotation?.bbox;
  if (!bbox) return '';
  return `${percent(bbox.xMin)}, ${percent(bbox.yMin)} - ${percent(bbox.xMax)}, ${percent(bbox.yMax)}`;
});

function coordinate(point: Point2D, axis: keyof Point2D) {
  return Math.round(point[axis] * 10000) / 100;
}

function updateCoordinate(point: AnnotationPointKey, axis: keyof Point2D, value: number | undefined) {
  const annotation = props.selectedAnnotation;
  if (!annotation) return;
  emit('update', annotation.id, {
    [point]: {
      ...annotation[point],
      [axis]: clamp01(Number(value ?? 0) / 100)
    }
  });
}

function updateField(key: 'refNo' | 'partName' | 'visible' | 'lineWidth' | 'fontSize', value: unknown) {
  const annotation = props.selectedAnnotation;
  if (!annotation) return;
  emit('update', annotation.id, { [key]: value });
}

function statusType(annotation: PatentAnnotation) {
  if (annotation.origin === 'manual') return 'info';
  if (annotation.reviewState === 'accepted') return 'success';
  if (annotation.reviewState === 'review') return 'warning';
  return 'info';
}

function statusLabel(annotation: PatentAnnotation) {
  if (annotation.origin === 'manual') return 'Manual';
  const confidence = annotation.confidence === undefined ? '' : ` ${Math.round(annotation.confidence * 100)}%`;
  if (annotation.reviewState === 'review') return `Review${confidence}`;
  return `Auto${confidence}`;
}

function acceptSelected() {
  const annotation = props.selectedAnnotation;
  if (!annotation) return;
  emit('update', annotation.id, { reviewState: 'accepted', reviewed: true });
}

function percent(value: number) {
  return `${Math.round(value * 1000) / 10}%`;
}
</script>

<template>
  <aside class="annotation-inspector">
    <section class="annotation-list-section">
      <div class="section-title">
        <span>Current page annotations</span>
        <ElTag size="small" type="info">{{ annotations.length }}</ElTag>
      </div>
      <ElScrollbar class="annotation-list">
        <ElEmpty v-if="!annotations.length" description="No annotations on this page" :image-size="52" />
        <template v-else>
          <button
            v-for="annotation in annotations"
            :key="annotation.id"
            type="button"
            class="annotation-row"
            :class="{ selected: annotation.id === selectedAnnotation?.id }"
            @click="emit('select', annotation.id)"
          >
            <span class="annotation-ref">{{ annotation.refNo || 'No ref' }}</span>
            <span class="annotation-name">{{ annotation.partName || 'Unnamed part' }}</span>
            <ElTag size="small" :type="statusType(annotation)">{{ statusLabel(annotation) }}</ElTag>
            <ElTag v-if="!annotation.visible" size="small" type="info">Hidden</ElTag>
          </button>
        </template>
      </ElScrollbar>
    </section>

    <section class="annotation-property-section">
      <div class="section-title">Annotation properties</div>
      <ElEmpty v-if="!selectedAnnotation" description="Select an annotation to edit it" :image-size="52" />
      <ElScrollbar v-else class="property-scroll">
        <ElForm label-position="top" size="small">
          <div class="two-columns">
            <ElFormItem label="Reference">
              <ElInput :model-value="selectedAnnotation.refNo" @update:model-value="updateField('refNo', $event)" />
            </ElFormItem>
            <ElFormItem label="Part name">
              <ElInput
                :model-value="selectedAnnotation.partName"
                @update:model-value="updateField('partName', $event)"
              />
            </ElFormItem>
          </div>

          <div v-for="point in ['anchor', 'elbow', 'label'] as AnnotationPointKey[]" :key="point">
            <div class="coordinate-title">{{ point }}</div>
            <div class="two-columns">
              <ElFormItem label="X (%)">
                <ElInputNumber
                  :model-value="coordinate(selectedAnnotation[point], 'x')"
                  :min="0"
                  :max="100"
                  :precision="2"
                  :controls="false"
                  @update:model-value="updateCoordinate(point, 'x', $event)"
                />
              </ElFormItem>
              <ElFormItem label="Y (%)">
                <ElInputNumber
                  :model-value="coordinate(selectedAnnotation[point], 'y')"
                  :min="0"
                  :max="100"
                  :precision="2"
                  :controls="false"
                  @update:model-value="updateCoordinate(point, 'y', $event)"
                />
              </ElFormItem>
            </div>
          </div>

          <div class="two-columns">
            <ElFormItem label="Line width">
              <ElInputNumber
                :model-value="selectedAnnotation.lineWidth"
                :min="0.5"
                :max="8"
                :step="0.1"
                :precision="1"
                @update:model-value="updateField('lineWidth', $event)"
              />
            </ElFormItem>
            <ElFormItem label="Font size">
              <ElInputNumber
                :model-value="selectedAnnotation.fontSize"
                :min="8"
                :max="72"
                :step="1"
                @update:model-value="updateField('fontSize', $event)"
              />
            </ElFormItem>
          </div>

          <ElFormItem label="Visible">
            <ElSwitch :model-value="selectedAnnotation.visible" @update:model-value="updateField('visible', $event)" />
          </ElFormItem>

          <div v-if="selectedAnnotation.origin === 'automatic'" class="auto-detail">
            <div class="detail-row">
              <span>Confidence</span>
              <strong>{{ selectedAnnotation.confidence === undefined ? '-' : `${Math.round(selectedAnnotation.confidence * 100)}%` }}</strong>
            </div>
            <div class="detail-row">
              <span>Status</span>
              <ElTag size="small" :type="statusType(selectedAnnotation)">{{ statusLabel(selectedAnnotation) }}</ElTag>
            </div>
            <div v-if="selectedAnnotation.modelName" class="detail-row">
              <span>Model</span>
              <strong>{{ selectedAnnotation.modelName }}</strong>
            </div>
            <div v-if="selectedAnnotation.modelReason" class="detail-reason">{{ selectedAnnotation.modelReason }}</div>
            <div v-if="selectedBboxText" class="detail-reason">bbox {{ selectedBboxText }}</div>
            <ElButton v-if="selectedAnnotation.reviewState === 'review'" type="success" plain class="delete-button" @click="acceptSelected">
              Accept
            </ElButton>
          </div>

          <ElButton type="danger" plain class="delete-button" @click="emit('delete', selectedAnnotation.id)">
            Delete annotation
          </ElButton>
        </ElForm>
      </ElScrollbar>
    </section>
  </aside>
</template>

<style scoped>
.annotation-inspector {
  display: grid;
  min-width: 0;
  min-height: 0;
  grid-template-rows: minmax(180px, 0.8fr) minmax(360px, 1.2fr);
  overflow: hidden;
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  background: var(--el-bg-color);
}

.annotation-list-section,
.annotation-property-section {
  display: flex;
  min-height: 0;
  flex-direction: column;
}

.annotation-list-section {
  border-bottom: 1px solid var(--el-border-color-light);
}

.section-title {
  display: flex;
  min-height: 42px;
  flex: 0 0 auto;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--el-border-color-lighter);
  padding: 0 14px;
  color: var(--el-text-color-primary);
  font-weight: 600;
}

.annotation-list,
.property-scroll {
  min-height: 0;
  flex: 1;
}

.annotation-row {
  display: grid;
  width: calc(100% - 16px);
  min-height: 42px;
  grid-template-columns: minmax(46px, auto) 1fr auto auto;
  align-items: center;
  gap: 8px;
  margin: 6px 8px;
  border: 1px solid transparent;
  border-radius: 6px;
  padding: 6px 9px;
  background: transparent;
  color: var(--el-text-color-regular);
  text-align: left;
  cursor: pointer;
}

.annotation-row:hover {
  background: var(--el-fill-color-light);
}

.annotation-row.selected {
  border-color: var(--el-color-primary-light-5);
  background: var(--el-color-primary-light-9);
}

.annotation-ref {
  color: var(--el-text-color-primary);
  font-weight: 700;
}

.annotation-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.property-scroll :deep(.el-scrollbar__view) {
  padding: 12px;
}

.two-columns {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.coordinate-title {
  margin: 2px 0 8px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
}

.annotation-property-section :deep(.el-input-number) {
  width: 100%;
}

.delete-button {
  width: 100%;
}

.auto-detail {
  display: grid;
  gap: 8px;
  margin-bottom: 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  padding: 10px;
  background: var(--el-fill-color-light);
}

.detail-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.detail-reason {
  color: var(--el-text-color-regular);
  font-size: 12px;
  line-height: 1.5;
  word-break: break-word;
}
</style>
