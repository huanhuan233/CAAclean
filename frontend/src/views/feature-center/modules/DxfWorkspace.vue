<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { polylinePath } from './dxf-path';

interface Entity {
  object_id: string;
  source_handle: string;
  layout: string;
  layer: string;
  type: string;
  status?: string;
  closed?: boolean;
  vertices?: number[][];
  start?: number[];
  end?: number[];
  point?: number[];
  center?: number[];
  radius?: number;
  start_angle?: number;
  end_angle?: number;
  length?: number | null;
  single_contour_area?: number | null;
  source_attributes?: Record<string, string>;
}
interface Document {
  revision_id: string;
  source_sha256: string;
  units: { code: number; source: string };
  layouts: Array<{ name: string }>;
  layers: Array<{ name: string; color: number; visible: boolean; source_defined: boolean }>;
  entities: Entity[];
  diagnostics: Array<Record<string, unknown>>;
  counts: Record<string, number>;
}
const props = defineProps<{ document: Document }>();
const query = ref('');
const typeFilter = ref('全部');
const layout = ref('Model');
const hidden = ref<string[]>([]);
const selectedId = ref('');
const zoom = ref(1);
const pan = ref<[number, number]>([0, 0]);
const drag = ref<[number, number] | null>(null);
watch(() => props.document.revision_id, () => {
  selectedId.value = '';
  hidden.value = [];
  zoom.value = 1;
  pan.value = [0, 0];
});
const entityTypes = computed(() => ['全部', ...new Set(props.document.entities.map(item => item.type))]);
const listed = computed(() => props.document.entities.filter(item => item.layout === layout.value &&
  (typeFilter.value === '全部' || item.type === typeFilter.value) &&
  (!query.value || `${item.source_handle} ${item.type} ${item.layer}`.toLowerCase().includes(query.value.toLowerCase()))));
const visible = computed(() => props.document.entities.filter(item => item.layout === layout.value &&
  !hidden.value.includes(item.layer) && !item.status));
const selected = computed(() => props.document.entities.find(item => item.object_id === selectedId.value) || null);
const points = computed(() => visible.value.flatMap(item => {
  if (item.vertices) return item.vertices.map(vertex => vertex.slice(0, 2));
  if (item.center && item.radius) return [[item.center[0] - item.radius, item.center[1] - item.radius],
    [item.center[0] + item.radius, item.center[1] + item.radius]];
  return [item.start, item.end, item.point].filter((value): value is number[] => Boolean(value));
}));
const bounds = computed(() => {
  const values = points.value;
  if (!values.length) return { x: 0, y: 0, width: 100, height: 100 };
  const xs = values.map(item => item[0]);
  const ys = values.map(item => item[1]);
  const x = Math.min(...xs);
  const y = Math.min(...ys);
  const width = Math.max(Math.max(...xs) - x, 1);
  const height = Math.max(Math.max(...ys) - y, 1);
  return { x, y, width, height };
});
const viewBox = computed(() => {
  const b = bounds.value;
  const margin = Math.max(b.width, b.height) * 0.04;
  const width = (b.width + margin * 2) / zoom.value;
  const height = (b.height + margin * 2) / zoom.value;
  return `${b.x - margin + (b.width + margin * 2 - width) / 2 + pan.value[0]} ${-(b.y + b.height + margin) +
    (b.height + margin * 2 - height) / 2 + pan.value[1]} ${width} ${height}`;
});
function path(item: Entity): string {
  if (item.vertices?.length) {
    return polylinePath(item.vertices, Boolean(item.closed));
  }
  if (item.start && item.end) return `M ${item.start[0]} ${-item.start[1]} L ${item.end[0]} ${-item.end[1]}`;
  if (item.center && item.radius) {
    if (item.type === 'CIRCLE') {
      const [x, y] = item.center;
      const r = item.radius;
      return `M ${x + r} ${-y} A ${r} ${r} 0 1 0 ${x - r} ${-y} A ${r} ${r} 0 1 0 ${x + r} ${-y}`;
    }
    const start = (item.start_angle || 0) * Math.PI / 180;
    const end = (item.end_angle || 0) * Math.PI / 180;
    const sweep = ((end - start) + Math.PI * 2) % (Math.PI * 2);
    const [x, y] = item.center;
    return `M ${x + item.radius * Math.cos(start)} ${-(y + item.radius * Math.sin(start))} A ${item.radius} ${item.radius} 0 ${sweep > Math.PI ? 1 : 0} 0 ${x + item.radius * Math.cos(end)} ${-(y + item.radius * Math.sin(end))}`;
  }
  return '';
}
function toggleLayer(name: string) {
  hidden.value = hidden.value.includes(name) ? hidden.value.filter(item => item !== name) : [...hidden.value, name];
  if (selected.value?.layer === name && hidden.value.includes(name)) selectedId.value = '';
}
function wheel(event: WheelEvent) {
  zoom.value = Math.max(0.05, Math.min(100, zoom.value * (event.deltaY < 0 ? 1.15 : 1 / 1.15)));
}
function move(event: PointerEvent) {
  if (!drag.value) return;
  const b = bounds.value;
  pan.value = [pan.value[0] - (event.clientX - drag.value[0]) * b.width / Math.max(event.currentTarget instanceof Element ? event.currentTarget.clientWidth : 1, 1) / zoom.value,
    pan.value[1] - (event.clientY - drag.value[1]) * b.height / Math.max(event.currentTarget instanceof Element ? event.currentTarget.clientHeight : 1, 1) / zoom.value];
  drag.value = [event.clientX, event.clientY];
}
const unitLabel = computed(() => ({ 1: '英寸', 4: '毫米', 5: '厘米', 6: '米' } as Record<number, string>)[props.document.units.code] || '图纸单位');
</script>

<template>
  <div class="dxf-workspace">
    <aside class="dxf-browser">
      <header><strong>图纸对象</strong><small>{{ document.counts.source_entities }} 个源图元</small></header>
      <div class="dxf-tools">
        <select v-model="layout"><option v-for="item in document.layouts" :key="item.name">{{ item.name }}</option></select>
        <input v-model="query" placeholder="搜索 handle、类型、图层" />
        <select v-model="typeFilter"><option v-for="item in entityTypes" :key="item">{{ item }}</option></select>
      </div>
      <div class="dxf-layers"><strong>图层</strong>
        <label v-for="item in document.layers.filter(layer => layer.source_defined)" :key="item.name">
          <input type="checkbox" :checked="!hidden.includes(item.name)" @change="toggleLayer(item.name)" />
          <span>{{ item.name }}</span><small>{{ document.entities.filter(entity => entity.layer === item.name).length }}</small>
        </label>
      </div>
      <div class="dxf-list">
        <button v-for="item in listed" :key="item.object_id" type="button" :class="{ selected: selectedId === item.object_id }"
          @click="selectedId = item.object_id">{{ item.type }} · {{ item.source_handle }} <small>{{ item.layer }}</small></button>
      </div>
    </aside>
    <div class="dxf-canvas"><div class="dxf-toolbar"><strong>{{ layout }}</strong><span>{{ unitLabel }}</span>
      <button type="button" @click="zoom = 1; pan = [0, 0]">适应图形</button></div>
      <svg :viewBox="viewBox" preserveAspectRatio="xMidYMid meet" @wheel.prevent="wheel"
        @pointerdown="drag = [$event.clientX, $event.clientY]" @pointermove="move" @pointerup="drag = null" @pointerleave="drag = null">
        <g v-for="item in visible" :key="item.object_id" @click.stop="selectedId = item.object_id">
          <path v-if="path(item)" :d="path(item)" fill="none" :stroke="selectedId === item.object_id ? '#f59e0b' : '#38bdf8'"
            :stroke-width="selectedId === item.object_id ? 2 : 1" vector-effect="non-scaling-stroke" />
          <path v-if="path(item)" :d="path(item)" fill="none" stroke="transparent" stroke-width="14"
            vector-effect="non-scaling-stroke" style="cursor:pointer" />
          <circle v-if="item.point" :cx="item.point[0]" :cy="-item.point[1]" r="3" fill="#38bdf8" vector-effect="non-scaling-stroke" />
        </g>
      </svg>
    </div>
    <aside class="dxf-detail"><strong>对象详情</strong>
      <template v-if="selected"><h3>{{ selected.type }} · {{ selected.source_handle }}</h3>
        <dl><dt>来源</dt><dd>DXF · {{ selected.layout }}</dd><dt>图层</dt><dd>{{ selected.layer }}</dd>
          <dt>闭合</dt><dd>{{ selected.closed == null ? '不适用' : selected.closed ? '是' : '否' }}</dd>
          <dt>顶点数</dt><dd>{{ selected.vertices?.length ?? '不适用' }}</dd>
          <dt>长度</dt><dd>{{ selected.length == null ? '未计算' : `${selected.length.toFixed(4)} ${unitLabel}` }}</dd>
          <dt>单轮廓面积</dt><dd>{{ selected.single_contour_area == null ? '未定义' : `${selected.single_contour_area.toFixed(4)} ${unitLabel}²` }}</dd>
          <dt>状态</dt><dd>{{ selected.status || '已解析' }}</dd></dl>
        <details><summary>源属性与顶点</summary><pre>{{ JSON.stringify({ source_attributes: selected.source_attributes, vertices: selected.vertices }, null, 2) }}</pre></details>
      </template><p v-else>在左侧列表或图形中选择图元</p>
      <p v-if="document.diagnostics.length">{{ document.diagnostics.length }} 条诊断记录</p>
    </aside>
  </div>
</template>

<style scoped>
.dxf-workspace{display:grid;grid-template-columns:260px minmax(0,1fr) 400px;min-height:0;flex:1;background:var(--el-bg-color);color:var(--el-text-color-primary)}
.dxf-browser,.dxf-detail{min-height:0;display:flex;flex-direction:column;padding:12px;gap:10px;border-right:1px solid var(--el-border-color);overflow:hidden}
.dxf-detail{border-right:0;border-left:1px solid var(--el-border-color);overflow:auto}
.dxf-browser header,.dxf-toolbar{display:flex;align-items:center;justify-content:space-between;gap:8px}
.dxf-tools{display:grid;gap:6px}.dxf-tools input,.dxf-tools select{width:100%;padding:6px;background:var(--el-fill-color-light);color:inherit;border:1px solid var(--el-border-color);border-radius:4px}
.dxf-layers{display:grid;gap:5px;max-height:160px;overflow:auto}.dxf-layers label{display:flex;gap:6px;align-items:center}.dxf-layers small{margin-left:auto}
.dxf-list{overflow:auto;display:flex;flex-direction:column;gap:2px}.dxf-list button{border:0;background:transparent;text-align:left;color:inherit;padding:7px;cursor:pointer}.dxf-list button.selected,.dxf-list button:hover{background:var(--el-color-primary-light-9)}.dxf-list small{float:right;color:var(--el-text-color-secondary)}
.dxf-canvas{min-width:0;min-height:0;display:flex;flex-direction:column;background:#111827}.dxf-toolbar{padding:8px 12px;background:var(--el-bg-color)}.dxf-canvas svg{width:100%;height:100%;touch-action:none}
.dxf-detail dl{display:grid;grid-template-columns:100px minmax(0,1fr);gap:8px;font-size:13px}.dxf-detail dd{margin:0;overflow-wrap:anywhere}.dxf-detail dt{color:var(--el-text-color-secondary)}.dxf-detail pre{overflow:auto;white-space:pre-wrap;font-size:11px}
@media(max-width:1050px){.dxf-workspace{grid-template-columns:220px minmax(0,1fr) 360px}}
</style>
