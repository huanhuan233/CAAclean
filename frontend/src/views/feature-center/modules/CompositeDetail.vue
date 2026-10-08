<script setup lang="ts">
import { computed } from 'vue';
import type { CompositeCoverageRecord, CompositeStructureRecord } from '@/service/api/cad';

const props = defineProps<{
  record: CompositeStructureRecord | null; loading: boolean; error: string;
  coverage: CompositeCoverageRecord | null; coverageLoading: boolean;
  coverageError: string; coverageComputing: boolean; selectedRegionId: string;
}>();
const emit = defineEmits<{
  recompute: [basis: 'cured' | 'uncured'];
  selectRegion: [regionId: string];
}>();
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
        <p v-if="record.nominal_direction?.status === 'derived_planar_nominal'">
          派生名义方向：{{ record.nominal_direction.angle_deg }}°；局部向量
          {{ record.nominal_direction.vector?.map(value => value.toFixed(3)).join('、') }}。
          箭头只表示轮廓起点的名义方向，不代表实际铺覆纤维轨迹。
        </p>
        <p v-else>局部方向未可用：{{ record.nominal_direction?.diagnostics?.join('、') || '缺少有效坐标花或参考面' }}。</p>
      </template>
      <p v-else>当前对象没有独立几何显示范围。</p>
      <p>树出现位置：{{ record.occurrence_ids.length }} 处，单层定义仍只计一次。</p>
      <template v-if="record.kind === 'group'">
        <h4>同一参考平面覆盖与名义厚度</h4>
        <p v-if="coverageLoading || coverageComputing">{{ coverageComputing ? '正在计算覆盖区域…' : '正在读取覆盖结果…' }}</p>
        <p v-else-if="coverageError">{{ coverageError }}</p>
        <p v-else-if="!coverage">尚无已发布的覆盖结果。需有原生层序、共同参考曲面和完整平面轮廓。</p>
        <template v-if="coverage">
          <p>口径：{{ coverage.thickness_basis === 'cured' ? '固化厚度' : '未固化厚度' }}；参考曲面：{{ coverage.reference_surface_object_id }}</p>
          <p>共 {{ coverage.cells.length }} 个已计算区域；这是名义叠层厚度，不是成品实测厚度。</p>
          <button v-for="cell in coverage.cells" :key="cell.region_id" type="button" class="region-row"
            :class="{ active: selectedRegionId === cell.region_id }" @click="emit('selectRegion', cell.region_id)">
            <strong>{{ cell.region_id }} · {{ cell.layer_count }} 层 · {{ cell.area_mm2.toLocaleString() }} mm²</strong>
            <span>{{ cell.thickness_status === 'complete' ? `${cell.nominal_thickness_mm} mm` :
              `已知 ${cell.known_thickness_subtotal_mm} mm，${cell.unknown_thickness_ply_object_ids.length} 层厚度未知` }}</span>
            <small>覆盖：{{ cell.ply_object_ids.join('、') }}</small>
          </button>
          <p v-if="selectedRegionId && coverage.cells.find(cell => cell.region_id === selectedRegionId)">
            当前区域：{{ selectedRegionId }}；{{ coverage.cells.find(cell => cell.region_id === selectedRegionId)?.contributions.map(
              item => `${item.ply_object_id} ${item.thickness_mm === null ? '厚度未知' : `${item.thickness_mm} mm`}`).join('；') }}
          </p>
          <p>铺层终止/覆盖变化边：{{ coverage.transitions.length }} 条（同层子片关系未验证时不据此判制造缺陷）。</p>
        </template>
        <div class="coverage-actions">
          <button type="button" :disabled="coverageComputing" @click="emit('recompute', 'cured')">计算固化厚度区域</button>
          <button type="button" :disabled="coverageComputing" @click="emit('recompute', 'uncured')">计算未固化厚度区域</button>
        </div>
      </template>
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
.region-row { display: flex; flex-direction: column; gap: 2px; width: 100%; margin: 4px 0; padding: 8px;
  border: 1px solid var(--el-border-color); border-radius: 6px; background: var(--el-fill-color-blank);
  text-align: left; color: var(--el-text-color-primary); cursor: pointer; }
.region-row.active { border-color: var(--el-color-primary); background: var(--el-color-primary-light-9); }
.region-row span, .region-row small { color: var(--el-text-color-secondary); }
.coverage-actions { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.coverage-actions button { border: 1px solid var(--el-border-color); border-radius: 4px; padding: 5px 7px;
  background: var(--el-fill-color-blank); color: var(--el-text-color-primary); cursor: pointer; }
</style>
