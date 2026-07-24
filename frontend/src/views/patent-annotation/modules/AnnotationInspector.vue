<script setup lang="ts">
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
</script>

<template>
  <aside class="annotation-inspector">
    <section class="annotation-list-section">
      <div class="section-title">
        <span>当前页标注</span>
        <ElTag size="small" type="info">{{ annotations.length }}</ElTag>
      </div>
      <ElScrollbar class="annotation-list">
        <ElEmpty v-if="!annotations.length" description="当前页暂无标注" :image-size="52" />
        <template v-else>
          <button
            v-for="annotation in annotations"
            :key="annotation.id"
            type="button"
            class="annotation-row"
            :class="{ selected: annotation.id === selectedAnnotation?.id }"
            @click="emit('select', annotation.id)"
          >
            <span class="annotation-ref">{{ annotation.refNo || '未编号' }}</span>
            <span class="annotation-name">{{ annotation.partName || '未填写部件名称' }}</span>
            <ElTag v-if="!annotation.visible" size="small" type="info">隐藏</ElTag>
          </button>
        </template>
      </ElScrollbar>
    </section>

    <section class="annotation-property-section">
      <div class="section-title">标注属性</div>
      <ElEmpty v-if="!selectedAnnotation" description="选择一条标注后编辑" :image-size="52" />
      <ElScrollbar v-else class="property-scroll">
        <ElForm label-position="top" size="small">
          <div class="two-columns">
            <ElFormItem label="编号">
              <ElInput :model-value="selectedAnnotation.refNo" @update:model-value="updateField('refNo', $event)" />
            </ElFormItem>
            <ElFormItem label="部件名称">
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
            <ElFormItem label="线宽">
              <ElInputNumber
                :model-value="selectedAnnotation.lineWidth"
                :min="0.5"
                :max="8"
                :step="0.1"
                :precision="1"
                @update:model-value="updateField('lineWidth', $event)"
              />
            </ElFormItem>
            <ElFormItem label="字号">
              <ElInputNumber
                :model-value="selectedAnnotation.fontSize"
                :min="8"
                :max="72"
                :step="1"
                @update:model-value="updateField('fontSize', $event)"
              />
            </ElFormItem>
          </div>

          <ElFormItem label="显示">
            <ElSwitch :model-value="selectedAnnotation.visible" @update:model-value="updateField('visible', $event)" />
          </ElFormItem>

          <ElButton type="danger" plain class="delete-button" @click="emit('delete', selectedAnnotation.id)">
            删除标注
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
  grid-template-columns: minmax(46px, auto) 1fr auto;
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
</style>
