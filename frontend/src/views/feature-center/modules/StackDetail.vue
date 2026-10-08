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
  <section class="composite-panel"><h4>结构信息</h4>
    <dl class="composite-fields"><dt>顺序状态</dt><dd>{{ orderStatus(record.order_status) }}</dd>
      <dt>直接成员</dt><dd>{{ children.length }} 个</dd></dl>
    <p v-if="record.order_status !== 'native_complete'" class="composite-muted">树出现顺序不能代替原生层序。</p>
  </section>
  <section v-if="parents.length" class="composite-panel"><h4>所属对象</h4>
    <CompositeMemberList :items="parents" empty-text="未取得所属对象" @select="emit('selectMember', $event)" />
  </section>
  <section class="composite-panel"><h4>直接成员</h4>
    <CompositeMemberList :items="children" empty-text="尚未取得直接成员引用" @select="emit('selectMember', $event)" />
  </section>
  <section class="composite-panel"><h4>原生扩展属性</h4>
    <p class="composite-muted">当前未采集到此对象的专用设计参数。</p>
  </section>
  <section class="composite-panel"><h4>几何与定位</h4>
    <p class="composite-muted">当前叠层没有独立可信的显示范围；可从直接成员查看已有几何。</p>
  </section>
</template>
