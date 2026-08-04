<script setup lang="ts">
export interface GizmoAxisPoint {
  x: number;
  y: number;
  depth: number;
}

defineOptions({ name: 'OrientationGizmo' });

defineProps<{ axes: Record<'x' | 'y' | 'z', GizmoAxisPoint> }>();
const emit = defineEmits<{ snap: [axis: 'x' | 'y' | 'z'] }>();
</script>

<template>
  <svg class="orientation-gizmo" viewBox="0 0 84 84" aria-label="视图方向坐标轴">
    <g
      v-for="axis in ['z', 'x', 'y'] as const"
      :key="axis"
      class="axis"
      :class="`axis-${axis}`"
      @click="emit('snap', axis)"
    >
      <line x1="42" y1="45" :x2="axes[axis].x" :y2="axes[axis].y" />
      <circle :cx="axes[axis].x" :cy="axes[axis].y" r="10" class="hit-area" />
      <text :x="axes[axis].x" :y="axes[axis].y" dy="4" text-anchor="middle">{{ axis.toUpperCase() }}</text>
    </g>
    <circle cx="42" cy="45" r="3" class="origin" />
  </svg>
</template>

<style scoped>
.orientation-gizmo {
  position: absolute;
  z-index: 4;
  bottom: 14px;
  left: 14px;
  width: 84px;
  height: 84px;
  overflow: visible;
  filter: drop-shadow(0 1px 2px rgb(15 23 42 / 18%));
  pointer-events: auto;
}
.axis {
  cursor: pointer;
}
.axis line {
  stroke-width: 2.4;
}
.axis text {
  font-size: 13px;
  font-weight: 700;
  paint-order: stroke;
  stroke: var(--el-bg-color);
  stroke-width: 3px;
}
.axis-x {
  color: #ef4444;
}
.axis-y {
  color: #22a447;
}
.axis-z {
  color: #1677ff;
}
.axis line,
.axis text {
  stroke: currentcolor;
  fill: currentcolor;
}
.axis .hit-area {
  fill: transparent;
  stroke: none;
}
.origin {
  fill: var(--el-text-color-primary);
}
</style>
