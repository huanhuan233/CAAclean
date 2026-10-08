<script setup lang="ts">
import { computed } from 'vue';
import type { CompositeStructureRecord } from '@/service/api/cad';

const props = defineProps<{ record: CompositeStructureRecord | null; loading: boolean; error: string }>();
const labels: Record<string, string> = {
  composite_material_name: '材料名称', composite_material_type: '材料类型',
  composite_cured_thickness: '固化厚度', composite_uncured_thickness: '未固化厚度',
  composite_orientation: '名义方向', composite_reference_surface: '参考曲面',
  composite_reference_surface_object_id: '参考曲面对象', composite_rosette_origin: '坐标花原点',
  composite_rosette_x: '坐标花 X 轴', composite_rosette_y: '坐标花 Y 轴',
  composite_draping_direction: '铺覆方向', composite_density: '材料密度',
  composite_area_m2: '原生单层面积'
};
const fields = computed(() => Object.entries(props.record?.fields || {})
  .filter(([key]) => key in labels).map(([key, field]) => ({ key, label: labels[key], ...field })));
const kindName: Record<string, string> = { stacking: '叠层', group: '铺层组', sequence: '序列', ply: '单层', cut_piece: '子片', cut_piece_group: '子片组' };
function value(field: { raw_value: unknown; raw_unit: string; normalized_value: number | null; normalized_unit: string; read_status: string }) {
  if (field.read_status !== 'available') return `读取状态：${field.read_status}`;
  if (field.normalized_value !== null) return `${field.normalized_value} ${field.normalized_unit}`;
  return `${String(field.raw_value ?? '')} ${field.raw_unit}`.trim() || '原生空值';
}
</script>

<template>
  <div class="composite-detail">
    <template v-if="record">
      <h3>{{ kindName[record.kind] || '复材对象' }} · {{ record.display_name || record.object_id }}</h3>
      <p>原生定义 ID：{{ record.object_id }}</p>
      <p>更新状态：{{ record.update_status || '未知' }}</p>
      <p v-if="record.kind !== 'ply'">层序：{{ record.order_status === 'native_complete' ? '原生顺序已读取' :
        record.order_status === 'partial' ? '部分可读' : '未取得，树顺序不可代替' }}</p>
      <p v-if="record.ordered_child_object_ids?.length">顺序成员：{{ record.ordered_child_object_ids.join(' → ') }}</p>
      <p v-if="record.parent_object_ids.length">所属对象：{{ record.parent_object_ids.join('、') }}</p>
      <h4>原生设计数据</h4>
      <dl v-if="fields.length"><template v-for="field in fields" :key="field.key">
        <dt>{{ field.label }}</dt><dd :title="`${field.source_api || ''} · ${field.raw_value ?? ''} ${field.raw_unit}`">{{ value(field) }}</dd>
      </template></dl>
      <p v-else>当前对象没有已采集的专用参数。</p>
      <h4>几何与来源</h4>
      <template v-if="record.kind === 'ply'">
        <p v-if="record.contour_planar_region?.status === 'derived_planar'">
          轮廓平面面积：{{ record.contour_planar_region.area_mm2?.toLocaleString() }} mm²
          <span v-if="record.contour_planar_region.area_error_bound_mm2">（误差界 ≤ {{ record.contour_planar_region.area_error_bound_mm2 }} mm²）</span>
        </p>
        <p v-else>轮廓平面面积：不可计算（{{ record.contour_planar_region?.diagnostics?.join('、') || '缺少有序轮廓' }}）</p>
        <p v-if="record.contour_planar_region?.status === 'derived_planar'">
          外轮廓 {{ record.contour_planar_region.outer_boundary_length_mm?.toLocaleString() }} mm；
          内轮廓 {{ record.contour_planar_region.inner_boundary_length_mm?.toLocaleString() }} mm；
          区域 {{ record.contour_planar_region.region_count }} 个，孔 {{ record.contour_planar_region.hole_count }} 个。
        </p>
        <p>单层曲面范围：{{ record.render_status === 'unavailable_without_verified_ply_mesh' ? '尚无独立可信网格映射' : record.render_status || '未验证' }}。</p>
        <p>中央视图仅预览原生轮廓；没有独立单层面片映射。平面面积不代表弯曲铺层的真实曲面面积。</p>
      </template>
      <p v-else>当前对象没有独立几何显示范围。</p>
      <p>树出现位置：{{ record.occurrence_ids.length }} 处，单层定义仍只计一次。</p>
      <details><summary>来源与诊断</summary><p>文档：{{ record.document_id }}</p>
        <p v-for="path in record.occurrence_paths" :key="path">{{ path }}</p>
        <p v-for="diagnostic in record.diagnostics" :key="diagnostic">{{ diagnostic }}</p>
      </details>
    </template>
    <p v-else-if="loading">正在读取单层详情…</p>
    <p v-else-if="error">{{ error }}</p>
  </div>
</template>

<style scoped>
.composite-detail { padding: 14px; overflow-y: auto; height: 100%; min-width: 0; color: var(--el-text-color-primary); }
.composite-detail h3 { font-size: 16px; margin: 0 0 12px; overflow-wrap: anywhere; }
.composite-detail h4 { font-size: 13px; margin: 18px 0 8px; }
.composite-detail p { font-size: 12px; overflow-wrap: anywhere; }
.composite-detail dl { display: grid; grid-template-columns: minmax(90px, 42%) minmax(0, 1fr); margin: 0; font-size: 12px; }
.composite-detail dt, .composite-detail dd { margin: 0; padding: 6px 2px; border-bottom: 1px solid var(--el-border-color-extra-light); overflow-wrap: anywhere; }
.composite-detail dt { color: var(--el-text-color-secondary); }
.composite-detail details { font-size: 11px; color: var(--el-text-color-secondary); overflow-wrap: anywhere; }
</style>
