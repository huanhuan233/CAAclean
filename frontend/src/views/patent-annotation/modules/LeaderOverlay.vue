<script setup lang="ts">
import { computed, ref } from 'vue';
import { clientPointToNormalized, normalizedPointToPixels } from '../geometry';
import type { AnnotationPointKey, AnnotationPointUpdate, PatentAnnotation, Point2D } from '../types';

defineOptions({ name: 'PatentLeaderOverlay' });

const props = withDefaults(
  defineProps<{
    annotations: PatentAnnotation[];
    selectedId?: string;
    stageWidth: number;
    stageHeight: number;
    interactive?: boolean;
  }>(),
  {
    selectedId: '',
    interactive: true
  }
);

const emit = defineEmits<{
  (event: 'select', annotationId: string): void;
  (event: 'update', payload: AnnotationPointUpdate): void;
}>();

const svgRef = ref<SVGSVGElement | null>(null);
const dragState = ref<{ pointerId: number; annotationId: string; point: AnnotationPointKey } | null>(null);

const visibleAnnotations = computed(() => props.annotations.filter(item => item.visible));
const selectedAnnotation = computed(() => visibleAnnotations.value.find(item => item.id === props.selectedId) ?? null);
const viewBox = computed(() => `0 0 ${Math.max(props.stageWidth, 1)} ${Math.max(props.stageHeight, 1)}`);

function toPixels(point: Point2D) {
  return normalizedPointToPixels(point, props.stageWidth, props.stageHeight);
}

function leaderPoints(annotation: PatentAnnotation) {
  const anchor = toPixels(annotation.anchor);
  const elbow = toPixels(annotation.elbow);
  const label = toPixels(annotation.label);
  return `${anchor.x},${anchor.y} ${elbow.x},${elbow.y} ${label.x},${label.y}`;
}

function selectAnnotation(annotationId: string) {
  if (!props.interactive) return;
  emit('select', annotationId);
}

function startHandleDrag(event: PointerEvent, point: AnnotationPointKey) {
  if (!props.interactive || !selectedAnnotation.value || !svgRef.value) return;
  event.preventDefault();
  event.stopPropagation();
  svgRef.value.setPointerCapture(event.pointerId);
  dragState.value = {
    pointerId: event.pointerId,
    annotationId: selectedAnnotation.value.id,
    point
  };
}

function moveHandle(event: PointerEvent) {
  const state = dragState.value;
  const svg = svgRef.value;
  if (!state || !svg || state.pointerId !== event.pointerId) return;
  event.preventDefault();
  emit('update', {
    id: state.annotationId,
    point: state.point,
    value: clientPointToNormalized(event.clientX, event.clientY, svg.getBoundingClientRect())
  });
}

function stopHandleDrag(event: PointerEvent) {
  const state = dragState.value;
  const svg = svgRef.value;
  if (!state || state.pointerId !== event.pointerId) return;
  if (svg?.hasPointerCapture(event.pointerId)) svg.releasePointerCapture(event.pointerId);
  dragState.value = null;
}
</script>

<template>
  <svg
    ref="svgRef"
    class="leader-overlay"
    :viewBox="viewBox"
    preserveAspectRatio="none"
    aria-label="专利附图标注层"
    @pointerdown.self="selectAnnotation('')"
    @pointermove="moveHandle"
    @pointerup="stopHandleDrag"
    @pointercancel="stopHandleDrag"
  >
    <g v-for="annotation in visibleAnnotations" :key="annotation.id">
      <polyline
        class="leader-line"
        :class="{ selected: annotation.id === selectedId }"
        :points="leaderPoints(annotation)"
        fill="none"
        vector-effect="non-scaling-stroke"
        :stroke-width="annotation.lineWidth"
        @pointerdown.stop="selectAnnotation(annotation.id)"
      />
      <circle
        class="anchor-dot"
        :class="{ selected: annotation.id === selectedId }"
        :cx="toPixels(annotation.anchor).x"
        :cy="toPixels(annotation.anchor).y"
        r="3"
        vector-effect="non-scaling-stroke"
        @pointerdown.stop="selectAnnotation(annotation.id)"
      />
      <text
        class="leader-label"
        :class="{ selected: annotation.id === selectedId }"
        :x="toPixels(annotation.label).x"
        :y="toPixels(annotation.label).y"
        :font-size="annotation.fontSize"
        dominant-baseline="central"
        @pointerdown.stop="selectAnnotation(annotation.id)"
      >
        {{ annotation.refNo }}
      </text>
    </g>

    <g v-if="selectedAnnotation" class="leader-handles">
      <circle
        v-for="point in ['anchor', 'elbow', 'label'] as AnnotationPointKey[]"
        :key="point"
        class="leader-handle"
        :cx="toPixels(selectedAnnotation[point]).x"
        :cy="toPixels(selectedAnnotation[point]).y"
        r="5"
        vector-effect="non-scaling-stroke"
        @pointerdown="startHandleDrag($event, point)"
      />
    </g>
  </svg>
</template>

<style scoped>
.leader-overlay {
  position: absolute;
  inset: 0;
  z-index: 2;
  width: 100%;
  height: 100%;
  overflow: visible;
  touch-action: none;
  user-select: none;
}

.leader-line {
  stroke: var(--el-text-color-primary);
  pointer-events: stroke;
  cursor: pointer;
}

.leader-line.selected {
  stroke: var(--el-color-primary);
}

.anchor-dot {
  fill: var(--el-text-color-primary);
  stroke: #fff;
  stroke-width: 1;
  cursor: pointer;
}

.anchor-dot.selected {
  fill: var(--el-color-primary);
}

.leader-label {
  fill: var(--el-text-color-primary);
  font-family: Arial, sans-serif;
  font-weight: 600;
  pointer-events: painted;
  cursor: pointer;
}

.leader-label.selected {
  fill: var(--el-color-primary);
}

.leader-handle {
  fill: #fff;
  stroke: var(--el-color-primary);
  stroke-width: 2;
  cursor: move;
}
</style>
