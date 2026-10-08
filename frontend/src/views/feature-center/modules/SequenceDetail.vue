<script setup lang="ts">
import { computed } from 'vue';
import type { CompositeStructureRecord } from '@/service/api/cad';
import CompositeMemberList from './CompositeMemberList.vue';
import { compositeMembers, compositeParentLinks, orderStatus } from './composite-view-model';

const props = defineProps<{ record: CompositeStructureRecord; relatedRecords: CompositeStructureRecord[] }>();
const emit = defineEmits<{ selectMember: [objectId: string] }>();
const children = computed(() => compositeMembers(props.record, props.relatedRecords));
const parents = computed(() => compositeParentLinks(props.record, props.relatedRecords));
</script>

<template>
  <section class="composite-panel"><h4>序列信息</h4>
    <dl class="composite-fields"><dt>层序来源</dt><dd>{{ orderStatus(record.order_status) }}</dd>
      <dt>直接单层</dt><dd>{{ children.length }} 个</dd></dl>
    <p v-if="record.order_status !== 'native_complete'" class="composite-muted">当前编号仅供浏览，不代表可靠叠放次序。</p>
  </section>
  <section class="composite-panel"><h4>所属铺层组</h4>
    <CompositeMemberList :items="parents" empty-text="所属组引用未取得" @select="emit('selectMember', $event)" />
  </section>
  <section class="composite-panel"><h4>顺序成员</h4>
    <CompositeMemberList :items="children" empty-text="尚未取得直接单层引用" @select="emit('selectMember', $event)" />
  </section>
  <section class="composite-panel"><h4>序列级原生属性</h4>
    <p class="composite-muted">当前未采集到此序列的专用设计参数。</p>
  </section>
  <section class="composite-panel"><h4>几何与定位</h4>
    <p class="composite-muted">当前序列没有独立可信的显示范围；可查看各单层的轮廓预览。</p>
  </section>
</template>
