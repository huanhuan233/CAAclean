<script setup lang="ts">
import { computed } from 'vue';
import type { CompositeStructureRecord } from '@/service/api/cad';
import CompositeFieldList from './CompositeFieldList.vue';
import CompositeMemberList from './CompositeMemberList.vue';
import {
  compositeFieldRows, compositeParentLinks, formatCompositeNumber
} from './composite-view-model';

const props = defineProps<{ record: CompositeStructureRecord; relatedRecords: CompositeStructureRecord[] }>();
const emit = defineEmits<{ selectMember: [objectId: string] }>();
const material = computed(() => compositeFieldRows(props.record, 'material'));
const geometry = computed(() => compositeFieldRows(props.record, 'geometry'));
const parents = computed(() => compositeParentLinks(props.record, props.relatedRecords));
const contour = computed(() => props.record.contour_planar_region);
const direction = computed(() => props.record.nominal_direction);
function measured(value: number | null | undefined, unit = ''): string {
  return value === null || value === undefined ? '未提供' : `${formatCompositeNumber(value)}${unit === '°' ? '°' : unit ? ` ${unit}` : ''}`;
}
</script>

<template>
  <section class="composite-panel"><h4>材料与铺层参数</h4>
    <CompositeFieldList :rows="material" empty-text="当前没有已采集的单层材料与铺层参数" />
  </section>
  <section class="composite-panel"><h4>原生几何与参考</h4>
    <CompositeFieldList :rows="geometry" empty-text="当前没有已采集的原生几何参数" />
    <div v-if="parents.length"><p class="composite-muted">所属对象</p>
      <CompositeMemberList :items="parents" empty-text="所属序列未取得" @select="emit('selectMember', $event)" /></div>
  </section>
  <section class="composite-panel"><h4>边界与几何测量</h4>
    <template v-if="contour?.status === 'derived_planar'">
      <dl class="composite-fields"><dt>轮廓平面面积</dt><dd>{{ measured(contour.area_mm2, 'mm²') }}</dd>
        <dt>外边界长度</dt><dd>{{ measured(contour.outer_boundary_length_mm, 'mm') }}</dd>
        <dt>内孔边界长度</dt><dd>{{ measured(contour.inner_boundary_length_mm, 'mm') }}</dd>
        <dt>区域数</dt><dd>{{ measured(contour.region_count) }}</dd>
        <dt>孔数</dt><dd>{{ measured(contour.hole_count) }}</dd></dl>
      <p class="composite-muted">由有序原生轮廓派生的平面区域；不作为弯曲铺层的真实曲面面积。</p>
    </template>
    <p v-else class="composite-muted">轮廓平面区域未取得：{{ contour?.diagnostics?.join('、') || '缺少可靠有序边界' }}</p>
  </section>
  <section class="composite-panel"><h4>局部名义方向</h4>
    <template v-if="direction?.status === 'derived_planar_nominal'">
      <dl class="composite-fields"><dt>派生角度</dt><dd>{{ measured(direction.angle_deg, '°') }}</dd>
        <dt>局部向量</dt><dd>{{ direction.vector?.map(value => formatCompositeNumber(value)).join('、') || '未提供' }}</dd>
        <dt>求值位置</dt><dd>轮廓起点</dd></dl>
      <p class="composite-muted">箭头只表示该位置的派生名义方向，不代表实际铺覆纤维轨迹。</p>
    </template>
    <p v-else class="composite-muted">局部方向未可用：{{ direction?.diagnostics?.join('、') || '缺少有效坐标花或参考面' }}</p>
  </section>
  <section class="composite-panel"><h4>三维显示能力</h4>
    <p v-if="contour?.status === 'derived_planar'">原生有序轮廓预览可用。</p>
    <p v-else class="composite-muted">轮廓预览不可用。</p>
    <p v-if="direction?.status === 'derived_planar_nominal'">派生名义方向箭头预览可用。</p>
    <p v-if="record.render_status === 'unavailable_without_verified_ply_mesh'" class="composite-muted">
      当前仅支持轮廓与方向预览；没有独立可信的单层曲面网格映射。</p>
    <p v-else-if="record.render_status" class="composite-muted">显示范围状态：{{ record.render_status }}</p>
  </section>
</template>
