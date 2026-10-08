<script setup lang="ts">
import { computed } from 'vue';
import type { CompositeCoverageRecord, CompositeStructureRecord } from '@/service/api/cad';
import CompositeFieldList from './CompositeFieldList.vue';
import CompositeMemberList from './CompositeMemberList.vue';
import {
  compositeFieldRows, compositeMembers, compositeParentLinks, formatCompositeNumber, orderStatus
} from './composite-view-model';

const props = defineProps<{
  record: CompositeStructureRecord; relatedRecords: CompositeStructureRecord[];
  coverage: CompositeCoverageRecord | null; coverageLoading: boolean;
  coverageError: string; coverageComputing: boolean; selectedRegionId: string;
}>();
const emit = defineEmits<{
  selectMember: [objectId: string]; recompute: [basis: 'cured' | 'uncured']; selectRegion: [regionId: string];
}>();
const members = computed(() => compositeMembers(props.record, props.relatedRecords));
const parents = computed(() => compositeParentLinks(props.record, props.relatedRecords));
const fields = computed(() => compositeFieldRows(props.record, 'group'));
const selectedRegion = computed(() => props.coverage?.cells.find(cell => cell.region_id === props.selectedRegionId));
</script>

<template>
  <section class="composite-panel"><h4>组级信息</h4>
    <dl class="composite-fields"><dt>成员顺序</dt><dd>{{ orderStatus(record.order_status) }}</dd>
      <dt>直接序列</dt><dd>{{ members.length }} 个</dd></dl>
  </section>
  <section class="composite-panel"><h4>所属叠层</h4>
    <CompositeMemberList :items="parents" empty-text="所属叠层引用未取得" @select="emit('selectMember', $event)" />
  </section>
  <section class="composite-panel"><h4>原生组级参数</h4>
    <CompositeFieldList :rows="fields" empty-text="当前未采集到组级设计参数" />
  </section>
  <section class="composite-panel"><h4>直接序列</h4>
    <CompositeMemberList :items="members" empty-text="尚未取得直接序列引用" @select="emit('selectMember', $event)" />
  </section>
  <section class="composite-panel"><h4>覆盖与名义厚度</h4>
    <p v-if="coverageComputing" class="composite-muted">正在计算覆盖区域…</p>
    <p v-else-if="coverageLoading" class="composite-muted">正在读取已发布结果…</p>
    <p v-if="coverageError" class="composite-muted">{{ coverageError }}</p>
    <template v-if="coverage">
      <p>口径：{{ coverage.thickness_basis === 'cured' ? '固化厚度' : '未固化厚度' }}；
        {{ coverage.cells.length }} 个区域</p>
      <p class="composite-muted">计算参考域：{{ coverage.reference_surface_object_id }}。厚度是名义叠层值，不是成品实测。</p>
      <p v-if="coverage.layer_order_status !== 'native_complete'" class="composite-muted">层序未确认；区域厚度为无序求和。</p>
      <button v-for="(cell, index) in coverage.cells" :key="cell.region_id" type="button" class="composite-region"
        :class="{ active: selectedRegionId === cell.region_id }" @click="emit('selectRegion', cell.region_id)">
        <strong>区域 {{ index + 1 }} · {{ cell.layer_count }} 层 · {{ formatCompositeNumber(cell.area_mm2) }} mm²</strong>
        <span>{{ cell.thickness_status === 'complete' && cell.nominal_thickness_mm !== null ? `${formatCompositeNumber(cell.nominal_thickness_mm)} mm` :
          `已知 ${formatCompositeNumber(cell.known_thickness_subtotal_mm)} mm；${cell.unknown_thickness_ply_object_ids.length} 层厚度未知` }}</span>
        <small :title="cell.ply_object_ids.join('、')">覆盖 {{ cell.ply_object_ids.length }} 个物理单层</small>
      </button>
      <p v-if="selectedRegion" class="composite-muted">所选区域：{{ selectedRegion.contributions.map(item =>
        `${item.ply_object_id} ${item.thickness_mm === null ? '厚度未知' : `${formatCompositeNumber(item.thickness_mm)} mm`}`).join('；') }}</p>
      <p class="composite-muted">内部覆盖变化边 {{ coverage.transitions.length }} 条；不据此直接判制造缺陷。</p>
    </template>
    <p v-else-if="!coverageLoading && !coverageError" class="composite-muted">尚无已发布覆盖结果。具备共同参考域和有效轮廓时可计算。</p>
    <div class="composite-actions">
      <button type="button" :disabled="coverageComputing" @click="emit('recompute', 'cured')">计算固化厚度区域</button>
      <button type="button" :disabled="coverageComputing" @click="emit('recompute', 'uncured')">计算未固化厚度区域</button>
    </div>
  </section>
  <section class="composite-panel"><h4>几何与定位</h4>
    <p class="composite-muted">铺层组本身没有独立可信的面片映射；区域结果仅显示已验证的共同平面范围。</p>
  </section>
</template>
