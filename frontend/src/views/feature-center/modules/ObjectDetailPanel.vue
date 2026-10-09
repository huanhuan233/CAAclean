<script setup lang="ts">
import { computed, defineComponent, h, resolveComponent } from 'vue';
import { ElTag, ElTooltip } from 'element-plus';
import type { GeometryQueryResponse, GeometryReferencePayload } from '@/service/api/cad';
import type { MbdAnnotationRecord, MbdNodeRecord, MbdRelationRecord } from '@/service/api/cad';
import type { CanonicalFeatureRecord } from './feature-center-bundle';
import type { RecognizedFeatureItem } from './recognized-feature-view-model';
import type { FeatureTreeNode, NativeFeatureRecord } from './native-feature-tree';
import type { DetailPanelLayout } from './detail-panel';
import type { SelectionContext, SelectionTarget } from './viewer-selection';
import type { MeasurementOperation } from './measurement-session';
import MeasurementPanel from './MeasurementPanel.vue';
import { mbdFieldName, mbdNodeKindName, mbdReadStatus, mbdSafeExternalUrl, mbdSemanticValue, mbdTypeName } from './mbd-view-model';
import {
  type DetailField,
  type GeometryLink,
  type ParameterField,
  bomRows,
  detailRowsFromRecord,
  faceRows,
  formatDetailValue,
  geometryLinksFor,
  nativeFeatureRows,
  nativePropertyValue,
  nativeSemanticParameterRows,
  normalizeParameterRows,
  parameterSourceFor,
  recognizedFeatureRows,
  selectionEvidenceRows
} from './object-detail-panel';

defineOptions({ name: 'ObjectDetailPanel' });

const props = defineProps<{
  contract: Api.ComponentBuild.ViewerContract | null;
  sourceFormat: 'STEP' | 'CATPART' | 'CATPRODUCT' | undefined;
  selectedTitle: string;
  detailLayout: DetailPanelLayout;
  primarySelection: SelectionTarget | null;
  selectionContext: SelectionContext;
  detailNode: Api.ComponentBuild.ViewerBomNode | null;
  detailParentNode: Api.ComponentBuild.ViewerBomNode | null;
  selectedNativeFeature: NativeFeatureRecord | null;
  nativeDetail: Api.ComponentBuild.NativeNodeProperties | null;
  nativeDetailLoading: boolean;
  nativeDetailError: string;
  selectedNativeTreeNode: FeatureTreeNode | null;
  selectedNativeTreeParent: FeatureTreeNode | null;
  selectedNativeParameterFamily: string;
  selectedNativeFaces: string[];
  selectedFeature: CanonicalFeatureRecord | null;
  mbdAnnotation: MbdAnnotationRecord | null;
  mbdNode: MbdNodeRecord | null;
  mbdRelations: MbdRelationRecord[];
  mbdDetailLoading: boolean;
  mbdDetailError: string;
  productPropertyDetail: Api.ComponentBuild.NativeNodeProperties | null;
  productPropertyLoading: boolean;
  productPropertyError: string;
  recognizedViewItems: RecognizedFeatureItem[];
  recognizedDetailLoading: boolean;
  recognizedDetailError: string;
  selectedFace: Record<string, unknown> | null;
  faceFeatureIds: string[];
  selectedMeasurements: Array<Record<string, unknown>>;
  mappingAvailable: boolean;
  isolated: boolean;
  transparent: boolean;
  geometryDetail: GeometryQueryResponse | null;
  geometryDetailLoading: boolean;
  geometryDetailError: string;
  measurementOperation: MeasurementOperation;
  measurementReferences: GeometryReferencePayload[];
  measurementResult: GeometryQueryResponse | null;
  measurementLoading: boolean;
  measurementError: string;
  geometrySnapshotAvailable: boolean;
  measurementSeedPoint: number[] | null;
  measurementSeedPoints: (number[] | null)[];
}>();

const emit = defineEmits<{
  close: [];
  highlight: [];
  toggleIsolated: [];
  toggleTransparent: [];
  openFeatureLinks: [];
  openNativeFace: [faceId: string];
  copy: [value: string];
  retryNativeDetail: [];
  retryRecognizedDetail: [];
  startMeasurement: [operation: Exclude<MeasurementOperation, 'idle'>];
  calculateMeasurement: [parameters: Record<string, unknown>];
  clearMeasurement: [];
  showNativeSketch: [];
  hideNativeSketch: [];
  openMbdRelation: [relation: MbdRelationRecord];
}>();

const nativeSketch = computed(() => {
  const feature = props.nativeDetail?.native_feature as Record<string, unknown> | undefined;
  const payload = feature?.native_sketch;
  return payload && typeof payload === 'object' ? payload as Record<string, unknown> : null;
});
const sketchElements = computed(() => Array.isArray(nativeSketch.value?.elements)
  ? nativeSketch.value.elements as Array<Record<string, unknown>> : []);
const sketchAxisRows = computed(() => {
  const axis = nativeSketch.value?.axis as Record<string, unknown> | undefined;
  if (!axis) return [];
  return [
    ['原点', axis.origin_mm], ['局部 X', axis.x_axis],
    ['局部 Y', axis.y_axis], ['法向', axis.normal]
  ].map(([label, value]) => ({ label, value: Array.isArray(value) ? value.join(', ') : '未采集' }));
});
const recognizedSegments = computed(() => {
  const payload = props.selectedFeature?.typed_payload?.geometry_recognition as Record<string, unknown> | undefined;
  return Array.isArray(payload?.segments) ? payload.segments as Array<Record<string, unknown>> : [];
});
const isMbdSelection = computed(() => props.primarySelection?.kind?.startsWith('mbd_') || false);
const mbdRawFields = computed(() => {
  const payload = props.mbdAnnotation?.semantic_payload;
  return Array.isArray(payload?.raw_fields) ? payload.raw_fields as Array<{
    key: string; raw_value: string; unit: string; read_status: string; source_api: string
  }> : [];
});

const sourceTypeLabel = computed(() => {
  if (props.sourceFormat === 'CATPRODUCT') return 'CATProduct';
  if (props.sourceFormat === 'CATPART') return 'CATPart';
  if (props.sourceFormat === 'STEP') return 'STEP';
  return '未加载';
});

const sourceTagLabel = computed(() => {
  if (isMbdSelection.value) return '原生 MBD';
  if (props.primarySelection?.kind === 'native_feature') return '原生特征';
  if (props.primarySelection?.kind === 'step_import_object' || props.primarySelection?.source === 'step_import') return 'STEP 导入对象';
  if (props.primarySelection?.kind === 'recognized_feature') return '识别特征';
  if (props.primarySelection?.kind === 'face') return '几何拓扑';
  if (props.primarySelection?.kind) return '模型对象';
  return props.contract?.native_semantics?.available ? '原生特征' : '模型对象';
});

const statusValue = computed(() => formatDetailValue(props.contract?.status || 'ready', 'status'));

const evidenceRows = computed(() => [
  ...selectionEvidenceRows(props.primarySelection, props.selectionContext),
  ...(props.primarySelection?.kind === 'recognized_feature' ? recognizedFeatureRows(props.selectedFeature) : [])
]);

const featureRows = computed<DetailField[]>(() => {
  if (isMbdSelection.value) return [];
  if (props.primarySelection?.kind === 'face') return props.selectedFace ? faceRows(props.selectedFace) : [];
  if (['step_import_object', 'edge', 'vertex', 'body', 'solid', 'loop', 'coedge'].includes(props.primarySelection?.kind || ''))
    return detailRowsFromRecord(props.primarySelection?.raw as Record<string, unknown> | null, []);
  if (props.selectedNativeFeature) {
    return nativeFeatureRows(
      props.selectedNativeFeature,
      props.selectedNativeTreeNode?.displayName,
      props.selectedNativeTreeParent?.displayName,
      props.selectedNativeParameterFamily
    );
  }
  if (props.selectedFeature) {
    const item = props.recognizedViewItems.find(view => view.featureId === props.selectedFeature?.feature_center_id);
    return item ? [
      { key: 'recognized_category', label: '类别', value: formatDetailValue(item.category) },
      { key: 'recognized_name', label: '特征名称', value: formatDetailValue(item.name) },
      { key: 'recognized_status', label: '核验状态', value: formatDetailValue(item.status.label) }
    ] : [];
  }
  if (props.selectedFace) return faceRows(props.selectedFace);
  return bomRows(props.detailNode as unknown as Record<string, unknown> | null);
});

const parameterRows = computed<ParameterField[]>(() => {
  if (isMbdSelection.value) return [];
  if (['step_import_object', 'face', 'edge', 'vertex', 'body', 'solid', 'loop', 'coedge'].includes(props.primarySelection?.kind || '')) return [];
  if (props.primarySelection?.kind === 'native_feature') {
    return props.nativeDetail ? nativeSemanticParameterRows(props.selectedNativeFeature) : [];
  }
  if (props.primarySelection?.kind === 'recognized_feature') {
    const source = parameterSourceFor(null, props.selectedFeature) as Record<string, unknown>;
    const labels: Record<string, string> = {
      diameter_mm: '直径 (mm)', cylindrical_wall_length_mm: '圆柱壁轴向长度 (mm)',
      radius_mm: '半径 (mm)', d1_mm: '第一侧退让距离 (mm)', d2_mm: '第二侧退让距离 (mm)',
      angle_deg: '倒角角度 (°)', angle_definition: '角度定义', mode: '尺寸模式',
      classification_status: '分类核验', render_range_status: '定位范围',
      depth_definition: '深度定义', end_states: '孔端局部状态',
      end_state_definition: '孔端判定依据', centerline_end_states: '中心线材料状态',
      end_boundary: '孔端关联边界', end_scan: '中心线材料区间',
      axis_direction: '轴向', start_point_mm: '起点 (mm)', end_point_mm: '终点 (mm)',
      length_mm: '长度 (mm)', width_mm: '宽度 (mm)', height_mm: '高度 (mm)', depth_mm: '深度 (mm)',
      bounded_cavity_volume_mm3: '按当前边界的型腔体积 (mm³)', volume_method: '体积方法',
      volume_status: '体积状态', cap_face_id: '顶面或底面', wall_face_ids: '侧壁',
      support_face_id: '支撑面', side_opening_face_ids: '侧向开口',
      dimension_method: '尺寸定义', height_definition: '高度或深度定义',
      profile_axis_ambiguous: '轮廓轴向是否不唯一',
      local_thickness_mm: '局部厚度 (mm)', thickness_start_mm: '厚度起点 (mm)',
      thickness_end_mm: '厚度终点 (mm)', thickness_direction: '厚度方向',
      thickness_method: '厚度测量方法', material_interval_mm: '连续材料区间 (mm)',
      geometry_form_status: '薄壁几何核验', structural_role_status: '结构角色判定',
      length_definition: '长度定义', root_support_face_id: '根部支撑面',
      parent_geometry_feature_id: '关联几何特征',
      free_edge_face_ids: '自由边侧面', connected_web_face_ids: '相连腹板',
      bounded_face_edge_lengths_mm: '参与面边长 (mm)',
      center_path_length_mm: '圆角中心路径长度 (mm)', center_path_length_definition: '中心路径定义',
      support_boundary_length_mm: '支撑边界长度 (mm)', cavity_role: '型腔内角色',
      cavity_role_status: '角色核验', cavity_floor_face_id: '型腔底面',
      cavity_wall_face_id: '型腔侧壁', cavity_opening_support_face_id: '开口支撑面',
      role_method: '角色判断方法', combined_measurements: '组合测量',
      combined_measurement_status: '组合测量状态',
      thin_wall_pair_id: '薄壁配对 ID', thickness_scope: '厚度适用范围',
      boss_to_rib_shortest_distance_mm: '凸台到筋主体最短距离 (mm)'
    };
    const rows = Object.entries(labels).filter(([key]) => Object.hasOwn(source, key) && key !== 'combined_measurements').map(([key, label]) => ({
      key, label, value: formatDetailValue(source[key], key)
    }));
    const combined = Array.isArray(source.combined_measurements) ? source.combined_measurements as Array<Record<string, unknown>> : [];
    const budget = source.combined_measurement_diagnostics as Record<string, unknown> | undefined;
    if (budget && Number(budget.unevaluated_count) > 0) {
      rows.push({ key: 'combined_budget', label: '候选/已算/未算',
        value: formatDetailValue(`${budget.candidate_total} / ${budget.evaluated_count} / ${budget.unevaluated_count}`) });
    }
    combined.forEach((item, index) => {
      const boss = props.recognizedViewItems.find(feature => feature.featureId === item.boss_feature_id);
      const rib = props.recognizedViewItems.find(feature => feature.featureId === item.rib_feature_id);
      rows.push({ key: `combined_${index}_boss`, label: '凸台对象',
        value: formatDetailValue(boss ? `${boss.title} · ${boss.featureId}` : String(item.boss_feature_id || '未加载')) });
      rows.push({ key: `combined_${index}_rib`, label: '筋对象',
        value: formatDetailValue(rib ? `${rib.title} · ${rib.featureId}` : String(item.rib_feature_id || '未加载')) });
      rows.push({ key: `combined_${index}_distance`, label: '凸台到筋主体最短距离 (mm)',
        value: formatDetailValue(item.distance_mm, 'distance_mm') });
      rows.push({ key: `combined_${index}_status`, label: '测量核验', value: formatDetailValue(item.status, 'status') });
      if (Object.hasOwn(item, 'within_tolerance'))
        rows.push({ key: `combined_${index}_near`, label: '在容差内', value: formatDetailValue(item.within_tolerance) });
      if (item.intersection_status)
        rows.push({ key: `combined_${index}_intersection`, label: '相交/接触判定',
          value: formatDetailValue(item.intersection_status, 'intersection_status') });
      if (Object.hasOwn(item, 'signed_proxy_clearance_mm'))
        rows.push({ key: `combined_${index}_proxy`, label: '代理有符号间隔 (mm)',
          value: formatDetailValue(item.signed_proxy_clearance_mm) });
      rows.push({ key: `combined_${index}_scope`, label: '测量范围', value: formatDetailValue(item.scope, 'scope') });
      rows.push({ key: `combined_${index}_start`, label: '凸台测量点 (mm)', value: formatDetailValue(item.start_point_mm, 'start_point_mm') });
      rows.push({ key: `combined_${index}_end`, label: '筋测量点 (mm)', value: formatDetailValue(item.end_point_mm, 'end_point_mm') });
    });
    return rows;
  }
  const rows = normalizeParameterRows(parameterSourceFor(props.selectedNativeFeature, props.selectedFeature));
  if (rows.length || !props.selectedMeasurements.length) return rows;
  return props.selectedMeasurements.flatMap((measurement, index) =>
    detailRowsFromRecord(measurement, ['name', 'value', 'unit', 'source', 'method', 'validity']).map(row => ({
      ...row,
      key: `measurement_${index}_${row.key}`,
      label: `${measurement.name || `测量 ${index + 1}`} · ${row.label}`
    }))
  );
});

const geometryDetailRows = computed<DetailField[]>(() =>
  props.geometryDetail?.status === 'success'
    ? detailRowsFromRecord(props.geometryDetail.values as Record<string, unknown> | null,
        ['kind', 'bounding_box'])
    : []
);

const nativePropertyRows = computed<DetailField[]>(() => {
  if (props.primarySelection?.kind !== 'native_feature') return [];
  return (props.nativeDetail?.tabs || []).flatMap(tab => tab.groups.flatMap(group => group.fields.map(field => ({
    key: `${tab.tab_id}/${group.group_id}/${field.property_id}`,
    label: `${group.group_label} · ${field.display_name || field.key}${field.display_unit || field.raw_unit ? ` (${field.display_unit || field.raw_unit})` : ''}`,
    value: nativePropertyValue(field)
  }))));
});
const productPropertyGroups = computed(() => {
  if (!props.primarySelection || !['assembly', 'part_instance', 'part'].includes(props.primarySelection.kind)) return [];
  const labels: Record<string, string> = {
    product_reference: '原生参考属性', product_instance: '原生实例属性',
    product_custom: '自定义产品属性', mbd_knowledge: 'MBD 知识参数'
  };
  return (props.productPropertyDetail?.tabs || []).flatMap(tab => tab.groups.map(group => ({
    key: `${tab.tab_id}/${group.group_id}`,
    title: labels[group.group_id] || group.group_label,
    rows: group.fields.map(field => {
      const value = nativePropertyValue(field);
      const path = field.key.startsWith('custom:') || field.key.startsWith('knowledge:') ? `\n原始路径：${field.key}` : '';
      return {
        key: field.property_id,
        label: field.display_name || field.key,
        value: { ...value, fullText: `${value.fullText}${path}\n来源：${field.source_api}` }
      };
    })
  })));
});

const geometryRows = computed<GeometryLink[]>(() =>
  geometryLinksFor({
    nativeFaceIds: props.selectedNativeFaces,
    recognizedFaceIds: props.selectedFeature?.geometry_refs?.face_ids || [],
    faceFeatureIds: props.faceFeatureIds,
    selectedFace: props.selectedFace as { boundary_edge_ids?: string[]; adjacent_face_ids?: string[] } | null
  })
);

const advancedRows = computed(() =>
  detailRowsFromRecord(
    (props.selectedFace || props.selectedNativeFeature || props.selectedFeature || props.detailNode) as Record<
      string,
      unknown
    > | null,
    []
  )
);

function hasGroup(group: string) {
  return props.detailLayout.groups.includes(group as never);
}

function copyValue(value: string) {
  emit('copy', value);
}

const StatusValue = defineComponent({
  name: 'StatusValue',
  props: {
    field: {
      type: Object as () => DetailField,
      required: true
    }
  },
  setup(props) {
    return () => {
      const value = props.field.value;
      const content = value.fullText;
      const inner = value.statusTone
        ? h(
            ElTag,
            { type: value.statusTone === 'primary' ? undefined : value.statusTone, effect: 'light', size: 'small' },
            () => value.text
          )
        : h('span', { class: ['field-value-text', { empty: value.empty }] }, value.text);
      return h(
        ElTooltip,
        { content, placement: 'top', showAfter: 450 },
        { default: () => h('span', { class: 'field-value' }, [inner]) }
      );
    };
  }
});

const DetailSection = defineComponent({
  name: 'DetailSection',
  props: {
    icon: {
      type: String,
      default: 'lucide:square-plus'
    },
    title: {
      type: String,
      default: ''
    },
    rows: {
      type: Array as () => DetailField[],
      required: true
    },
    emptyText: {
      type: String,
      required: true
    },
    embedded: {
      type: Boolean,
      default: false
    },
    collapsed: { type: Boolean, default: false }
  },
  setup(props) {
    const SvgIconComponent = resolveComponent('SvgIcon');
    return () =>
      h('section', { class: ['detail-section-v2', { embedded: props.embedded }] }, [
        h('details', { open: !props.embedded && !props.collapsed }, [
          props.title
            ? h('summary', { class: 'section-heading' }, [
                h('span', { class: 'section-title' }, [
                  h(SvgIconComponent, { icon: props.icon }),
                  h('span', props.title),
                ]),
                h(SvgIconComponent, { class: 'section-chevron', icon: 'lucide:chevron-down' })
              ])
            : null,
          h('div', { class: 'section-content' }, [
            props.rows.length
              ? h(
                  'div',
                  { class: 'field-list' },
                  props.rows.map(row =>
                    h('div', { key: row.key, class: 'field-row' }, [
                      h(
                        ElTooltip,
                        { content: row.label, placement: 'top', showAfter: 450 },
                        {
                          default: () => h('span', { class: 'field-label' }, row.label)
                        }
                      ),
                      h(StatusValue, { field: row })
                    ])
                  )
                )
              : h('div', { class: 'compact-empty' }, props.emptyText)
          ])
        ])
      ]);
  }
});
</script>

<template>
  <div class="object-detail-panel">
    <header class="object-detail-header">
      <strong>对象详情</strong>
      <ElTooltip content="关闭详情" placement="left">
        <ElButton class="header-icon-button" circle text aria-label="关闭详情" @click="emit('close')">
          <SvgIcon icon="lucide:x" />
        </ElButton>
      </ElTooltip>
    </header>

    <ElScrollbar class="object-detail-scrollbar">
      <div class="object-detail-body">
        <section v-if="contract" class="object-summary-card">
          <span class="summary-icon">
            <SvgIcon icon="lucide:box" />
          </span>
          <div class="summary-copy">
            <ElTooltip :content="selectedTitle || contract.summary.model_name" placement="top" :show-after="350">
              <strong>{{ selectedTitle || contract.summary.model_name }}</strong>
            </ElTooltip>
            <span>{{ sourceTypeLabel }}</span>
          </div>
          <div class="summary-tags">
            <ElTag effect="light" size="small">{{ sourceTagLabel }}</ElTag>
            <ElTag :type="statusValue.statusTone === 'success' ? 'success' : 'info'" effect="light" size="small">
              {{ statusValue.text }}
            </ElTag>
          </div>
        </section>
        <div v-else class="compact-empty">当前对象不存在</div>

        <section v-if="isMbdSelection && mbdDetailLoading" class="compact-empty">正在读取 MBD 原生详情…</section>
        <section v-if="productPropertyLoading" class="compact-empty">正在读取产品原生属性…</section>
        <section v-if="productPropertyError" class="compact-empty">{{ productPropertyError }}</section>
        <DetailSection v-for="group in productPropertyGroups" :key="group.key" :title="group.title"
          icon="lucide:tag" :rows="group.rows" empty-text="本组无可读字段" />
        <section v-if="isMbdSelection && mbdDetailError" class="compact-empty">{{ mbdDetailError }}</section>
        <section v-if="mbdAnnotation" class="detail-section-v2 mbd-detail">
          <details open>
            <summary class="section-heading"><span class="section-title">{{ mbdTypeName(mbdAnnotation.component_kind) }}</span></summary>
            <div class="section-content">
              <div class="parameter-row"><span>读取状态</span><ElTag size="small" :type="mbdReadStatus(mbdAnnotation.read_status).tone">{{ mbdReadStatus(mbdAnnotation.read_status).label }}</ElTag></div>
              <div class="parameter-row"><span>所属标注集</span><span>{{ mbdAnnotation.fta_set_id }}</span></div>
              <div v-if="mbdAnnotation.annotation_text_status === 'available'" class="mbd-body-text">{{ mbdAnnotation.annotation_text }}</div>
              <p v-else class="compact-empty">原生正文：{{ mbdAnnotation.annotation_text_status || '未读取' }}</p>
              <div v-for="field in mbdRawFields" :key="field.key" class="parameter-row">
                <span>{{ mbdFieldName(field.key) }}</span>
                <a v-if="field.key.startsWith('external_url_') && mbdSafeExternalUrl(field.raw_value)"
                   :href="mbdSafeExternalUrl(field.raw_value) || undefined" target="_blank" rel="noopener noreferrer">
                  {{ field.raw_value }}
                </a>
                <span v-else class="mbd-field-value">{{ field.read_status === 'available' ? `${field.raw_value}${field.unit ? ` ${field.unit}` : ''}` : mbdReadStatus(field.read_status).label }}</span>
              </div>
              <p class="compact-empty">原生 TTRS：{{ mbdSemanticValue(mbdAnnotation, 'annotation_ttrs_count') ?? '未读取' }} · {{ mbdSemanticValue(mbdAnnotation, 'native_geometry_link_status') || '未解析' }}</p>
              <p class="compact-empty">显示几何：未建立可信映射，当前不执行精确三维定位。</p>
            </div>
          </details>
        </section>
        <section v-if="mbdNode" class="detail-section-v2 mbd-detail">
          <details open>
            <summary class="section-heading"><span class="section-title">标注层级与视图</span></summary>
            <div class="section-content">
              <div class="parameter-row"><span>类型</span><span>{{ mbdNodeKindName(mbdNode.pmi_kind) }}</span></div>
              <div class="parameter-row"><span>所属文档</span><span>{{ mbdNode.owning_document_id || '未解析' }}</span></div>
              <div class="parameter-row"><span>归属依据</span><span>{{ mbdNode.ownership_status || '未解析' }}</span></div>
              <template v-if="mbdNode.pmi_kind === 'fta_view'">
                <div class="parameter-row"><span>坐标状态</span><span>{{ mbdNode.coordinate_frame_status || '未读取' }}</span></div>
                <div class="parameter-row"><span>原点</span><span>{{ mbdNode.plane_origin || '未读取' }}</span></div>
                <div class="parameter-row"><span>局部 X</span><span>{{ mbdNode.plane_x_axis || '未读取' }}</span></div>
                <div class="parameter-row"><span>局部 Y</span><span>{{ mbdNode.plane_y_axis || '未读取' }}</span></div>
                <div class="parameter-row"><span>法向</span><span>{{ mbdNode.plane_normal || '未读取' }}</span></div>
              </template>
              <div v-if="mbdNode.pmi_kind === 'fta_capture'" class="parameter-row"><span>相机</span><span>{{ mbdNode.camera_status || '未读取' }}</span></div>
              <p class="compact-empty">仅保留实际取得的原生视图事实；不自动更改当前相机。</p>
            </div>
          </details>
        </section>
        <section v-if="isMbdSelection && mbdRelations.length" class="detail-section-v2 mbd-detail">
          <details open>
            <summary class="section-heading"><span class="section-title">集合与捕获关系</span></summary>
            <div class="section-content">
              <button v-for="(relation, index) in mbdRelations" :key="`${relation.pmi_id}:${relation.target_id}:${index}`"
                type="button" class="geometry-link" @click="emit('openMbdRelation', relation)">
                <span>{{ relation.association_kind }}</span><strong>{{ primarySelection?.id === relation.pmi_id ? relation.target_id : relation.pmi_id }}</strong>
              </button>
            </div>
          </details>
        </section>

        <DetailSection v-if="geometryDetailRows.length" title="几何参数" icon="lucide:hexagon" :rows="geometryDetailRows" empty-text="暂无几何参数" />
        <section v-if="geometryDetailLoading" class="compact-empty">正在读取 B-Rep 几何…</section>
        <section v-if="geometryDetailError" class="compact-empty">{{ geometryDetailError }}</section>
        <DetailSection v-if="featureRows.length" :title="primarySelection?.kind === 'face' ? '面拓扑' : '对象属性'" icon="lucide:square-plus" :rows="featureRows" empty-text="暂无对象属性" />
        <p v-if="primarySelection?.source === 'topology' && selectionContext.mappingStatus === 'unavailable'" class="compact-empty">
          当前对象没有可信局部显示映射，可查看属性，暂不能在模型中精确定位。
        </p>

        <section v-if="primarySelection?.kind === 'native_feature' && selectionContext.mappingStatus === 'candidate'" class="detail-section-v2">
          <ElTag type="warning">候选高亮，有误选风险；不是确认的建模历史归属</ElTag>
        </section>
        <section v-else-if="selectionContext.mappingAuthority === 'canvas_hit_preview' || selectionContext.mappingAuthority === 'whole_part_preview'" class="detail-section-v2">
          <ElTag type="warning">{{ selectionContext.mappingAuthority === 'whole_part_preview' ? '整件预览高亮，未确认特征范围' : '仅预览高亮点击的网格，未确认完整零件范围' }}</ElTag>
        </section>

        <section v-if="primarySelection?.kind === 'native_feature' && nativeDetailLoading" class="compact-empty">正在读取数据库详情…</section>
        <section v-if="primarySelection?.kind === 'native_feature' && nativeDetailError" class="detail-section-v2">
          <span>数据库详情读取失败：{{ nativeDetailError }}</span>
          <ElButton size="small" @click="emit('retryNativeDetail')">重试</ElButton>
        </section>
        <section v-if="primarySelection?.kind === 'recognized_feature' && recognizedDetailLoading" class="compact-empty">正在读取识别详情…</section>
        <section v-if="primarySelection?.kind === 'recognized_feature' && recognizedDetailError" class="detail-section-v2">
          <span>识别详情读取失败：{{ recognizedDetailError }}</span>
          <ElButton size="small" @click="emit('retryRecognizedDetail')">重试</ElButton>
        </section>
        <DetailSection v-if="primarySelection?.kind === 'native_feature' && nativeDetail" title="CATIA 属性" icon="lucide:square-plus" :rows="nativePropertyRows" empty-text="未采集到通用属性" />
        <section v-if="primarySelection?.kind === 'native_feature' && nativeSketch" class="detail-section-v2">
          <details open>
            <summary class="section-heading"><span class="section-title">草图几何</span></summary>
            <div class="section-content">
              <p>支撑：{{ nativeSketch.support_reference_status || '未核验' }}</p>
              <div v-for="row in sketchAxisRows" :key="String(row.label)" class="parameter-row">
                <span>{{ row.label }}</span><span>{{ row.value }}</span>
              </div>
              <p>元素：{{ sketchElements.length }}；连接关系：{{ nativeSketch.connection_status || '未核验' }}</p>
              <div class="measurement-actions">
                <ElButton size="small" type="primary" @click="emit('showNativeSketch')">显示草图</ElButton>
                <ElButton size="small" @click="emit('hideNativeSketch')">隐藏</ElButton>
              </div>
              <details><summary>实际元素</summary>
                <div v-for="element in sketchElements" :key="String(element.element_id)" class="parameter-row">
                  <span>{{ element.kind }} · {{ element.element_id }}</span>
                  <span>{{ element.construction ? '构造' : '轮廓' }}</span>
                </div>
              </details>
              <p class="compact-empty">仅显示已采集几何；未执行完整约束求解。</p>
            </div>
          </details>
        </section>

        <section v-if="primarySelection?.kind === 'recognized_feature' && recognizedSegments.length" class="detail-section-v2">
          <details open>
            <summary class="section-heading"><span class="section-title">孔段与深度</span></summary>
            <div class="section-content">
              <div v-for="(segment, index) in recognizedSegments" :key="index" class="parameter-list-v2">
                <strong>第 {{ index + 1 }} 段</strong>
                <div class="parameter-row"><span>直径</span><span>{{ segment.diameter_mm }} mm</span></div>
                <div class="parameter-row"><span>圆柱壁轴向长度</span><span>{{ segment.cylindrical_wall_length_mm }} mm</span></div>
                <div class="parameter-row"><span>起点</span><span>{{ Array.isArray(segment.start_point_mm) ? segment.start_point_mm.join(', ') : '未核验' }}</span></div>
                <div class="parameter-row"><span>终点</span><span>{{ Array.isArray(segment.end_point_mm) ? segment.end_point_mm.join(', ') : '未核验' }}</span></div>
              </div>
            </div>
          </details>
        </section>
        <section v-if="primarySelection?.kind === 'recognized_feature' && selectedMeasurements.length" class="detail-section-v2">
          <details open>
            <summary class="section-heading"><span class="section-title">几何测量</span></summary>
            <div class="section-content">
              <div v-for="(measurement, index) in selectedMeasurements" :key="String(measurement.measurement_id || index)" class="parameter-row">
                <span>{{ measurement.name === 'diameter' ? '实测直径' : measurement.name === 'cylindrical_wall_length' ? '实测圆柱壁长度' : measurement.name }}</span>
                <span>{{ measurement.value }} {{ measurement.unit }} · {{ measurement.validity }}</span>
              </div>
            </div>
          </details>
        </section>

        <section v-if="primarySelection?.kind === 'native_feature' || primarySelection?.kind === 'recognized_feature'" class="detail-section-v2">
          <details open>
            <summary class="section-heading">
              <span class="section-title">
                <SvgIcon icon="lucide:hexagon" />
                <span>特征参数</span>
              </span>
              <SvgIcon class="section-chevron" icon="lucide:chevron-down" />
            </summary>
            <div class="section-content">
              <div v-if="parameterRows.length" class="parameter-list-v2">
                <div v-for="row in parameterRows" :key="row.key" class="parameter-row">
                  <ElTooltip :content="row.label" placement="top" :show-after="450">
                    <span class="field-label">{{ row.label }}</span>
                  </ElTooltip>
                  <StatusValue :field="row" />
                  <ElTooltip content="复制完整值" placement="top">
                    <ElButton
                      class="copy-button"
                      text
                      circle
                      aria-label="复制参数值"
                      @click="copyValue(row.value.fullText)"
                    >
                      <SvgIcon icon="lucide:copy" />
                    </ElButton>
                  </ElTooltip>
                </div>
              </div>
              <div v-else class="compact-empty">{{ nativeDetail?.native_feature_status === 'not_imported' ? '专用语义尚未入库' : selectedNativeFeature?.decode_level === 'type_only' ? '仅识别类型，专用参数尚未解码' : '未采集到专用参数' }}</div>
            </div>
          </details>
        </section>

        <MeasurementPanel v-if="!isMbdSelection"
          :operation="measurementOperation"
          :references="measurementReferences"
          :result="measurementResult"
          :loading="measurementLoading"
          :error="measurementError"
          :snapshot-available="geometrySnapshotAvailable"
          :seed-point="measurementSeedPoint"
          :seed-points="measurementSeedPoints"
          @start="emit('startMeasurement', $event)"
          @calculate="emit('calculateMeasurement', $event)"
          @clear="emit('clearMeasurement')"
        />

        <section v-if="!isMbdSelection" class="detail-section-v2">
          <details>
            <summary class="section-heading">
              <span class="section-title">
                <SvgIcon icon="lucide:square-plus" />
                <span>关联几何</span>
                <span v-if="geometryRows.length" class="section-count">{{ geometryRows.length }}</span>
              </span>
              <SvgIcon class="section-chevron" icon="lucide:chevron-down" />
            </summary>
            <div class="section-content">
              <div v-if="geometryRows.length" class="geometry-link-list">
                <button
                  v-for="link in geometryRows"
                  :key="`${link.kind}-${link.id}`"
                  type="button"
                  class="geometry-link"
                  :disabled="!link.clickable"
                  @click="link.clickable && emit('openNativeFace', link.id)"
                >
                  <span>{{ link.kind }}</span>
                  <strong>{{ link.id }}</strong>
                </button>
              </div>
              <div v-else class="geometry-empty">未建立关联面</div>
            </div>
          </details>
        </section>

        <section v-if="!isMbdSelection && hasGroup('operations')" class="detail-section-v2 actions-v2">
          <details open>
            <summary class="section-heading">
              <span class="section-title">
                <SvgIcon icon="lucide:bolt" />
                <span>快捷操作</span>
              </span>
              <SvgIcon class="section-chevron" icon="lucide:chevron-down" />
            </summary>
            <div class="section-content">
              <div class="action-grid">
                <ElButton size="small" @click="emit('highlight')">
                  <template #icon><SvgIcon icon="lucide:sparkles" /></template>
                  高亮
                </ElButton>
                <ElButton size="small" :type="isolated ? 'primary' : 'default'" @click="emit('toggleIsolated')">
                  <template #icon><SvgIcon icon="lucide:focus" /></template>
                  隔离
                </ElButton>
                <ElButton size="small" :type="transparent ? 'primary' : 'default'" @click="emit('toggleTransparent')">
                  <template #icon><SvgIcon icon="lucide:blend" /></template>
                  透明
                </ElButton>
                <ElButton
                  v-if="hasGroup('source')"
                  size="small"
                  :disabled="!detailLayout.featureLinkEnabled"
                  @click="emit('openFeatureLinks')"
                >
                  <template #icon><SvgIcon icon="lucide:waypoints" /></template>
                  {{ detailLayout.featureLinkLabel }}
                </ElButton>
              </div>
            </div>
          </details>
        </section>

        <ElCollapse v-if="hasGroup('topology')" class="advanced-v2">
          <ElCollapseItem title="高级拓扑信息" name="topology">
            <DetailSection title="" :rows="advancedRows" empty-text="暂无高级拓扑信息" embedded />
          </ElCollapseItem>
        </ElCollapse>
        <DetailSection v-if="primarySelection" title="来源与诊断" icon="lucide:info" :rows="evidenceRows" empty-text="暂无映射证据" collapsed />
      </div>
    </ElScrollbar>
  </div>
</template>

<style>
.mbd-detail .mbd-body-text { white-space: pre-wrap; overflow-wrap: anywhere; padding: 8px 0; color: var(--el-text-color-primary); }
.mbd-detail .mbd-field-value { white-space: pre-wrap; overflow-wrap: anywhere; text-align: right; }
.mbd-detail .parameter-row { min-width: 0; }
.mbd-detail a { overflow-wrap: anywhere; word-break: break-word; }
.object-detail-panel {
  display: flex;
  height: 100%;
  min-width: 0;
  flex-direction: column;
  background: var(--el-bg-color);
  color: var(--el-text-color-primary);
}

.object-detail-header {
  display: flex;
  min-height: 64px;
  flex: 0 0 auto;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--el-border-color-light);
  background: var(--el-bg-color);
  padding: 0 14px 0 18px;
}

.object-detail-header strong {
  font-size: 22px;
  font-weight: 700;
  line-height: 30px;
}

.header-icon-button {
  color: var(--el-text-color-secondary);
}

.header-icon-button:hover,
.header-icon-button:focus-visible {
  color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}

.object-detail-scrollbar {
  min-height: 0;
  flex: 1;
}

.object-detail-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 14px 14px 16px;
}

.object-summary-card,
.detail-section-v2 {
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  background: var(--el-bg-color-overlay);
}

.object-summary-card {
  display: grid;
  grid-template-columns: 56px minmax(0, 1fr);
  gap: 6px 14px;
  padding: 16px;
}

.summary-icon {
  display: grid;
  width: 48px;
  height: 48px;
  border-radius: 10px;
  color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
  font-size: 30px;
  place-items: center;
}

.summary-copy {
  min-width: 0;
}

.summary-copy strong,
.summary-copy span {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.summary-copy strong {
  font-size: 19px;
  font-weight: 700;
  line-height: 25px;
}

.summary-copy span {
  color: var(--el-text-color-secondary);
  font-size: 13px;
  line-height: 20px;
}

.summary-tags {
  display: flex;
  min-width: 0;
  grid-column: 2;
  gap: 6px;
  flex-wrap: wrap;
  padding-top: 2px;
}

.summary-tags :deep(.el-tag:first-child) {
  border-color: var(--el-color-primary-light-5);
  color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}

.summary-tags :deep(.el-tag) {
  font-size: 12px;
  line-height: 20px;
}

.detail-section-v2 {
  padding: 0;
}

.detail-section-v2.embedded {
  border: 0;
  padding: 0;
}

.detail-section-v2 details {
  min-width: 0;
}

.detail-section-v2 summary {
  display: flex;
  width: 100%;
  box-sizing: border-box;
  align-items: center;
  list-style: none;
}

.detail-section-v2 summary::-webkit-details-marker {
  display: none;
}

.detail-section-v2 summary::marker {
  content: '';
}

.section-heading {
  display: flex;
  min-height: 52px;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--el-border-color-light);
  cursor: pointer;
  padding: 0 18px;
  user-select: none;
}

.section-title {
  display: inline-flex;
  min-width: 0;
  align-items: center;
  gap: 10px;
  color: var(--el-text-color-primary);
  font-size: 16px;
  font-weight: 650;
  line-height: 24px;
}

.section-title :deep(.svg-icon) {
  flex: 0 0 auto;
  color: var(--el-color-primary);
  font-size: 18px;
}

.section-count {
  display: inline-flex;
  min-width: 26px;
  height: 26px;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
  font-size: 13px;
  font-weight: 700;
  padding: 0 8px;
}

.section-chevron {
  flex: 0 0 auto;
  color: var(--el-text-color-primary);
  font-size: 18px;
  transition: transform 0.16s ease;
}

.detail-section-v2 details:not([open]) .section-heading {
  border-bottom-color: transparent;
}

.detail-section-v2 details:not([open]) .section-chevron {
  transform: rotate(-90deg);
}

.section-content {
  min-width: 0;
  padding: 12px 20px 15px;
}

.field-list,
.parameter-list-v2 {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 7px;
}

.field-row,
.parameter-row {
  display: grid;
  min-height: 48px;
  min-width: 0;
  align-items: center;
  gap: 14px;
}

.field-row {
  grid-template-columns: minmax(122px, 37%) minmax(0, 1fr);
  column-gap: 28px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.parameter-row {
  grid-template-columns: minmax(132px, 38%) minmax(0, 1fr) 36px;
  gap: 0;
  border: 1px solid var(--el-border-color-light);
  border-radius: 6px;
  background: var(--el-bg-color);
  overflow: hidden;
}

.field-row:last-child {
  border-bottom: 0;
}

.field-label {
  min-width: 0;
  overflow-wrap: anywhere;
  color: var(--el-text-color-secondary);
  font-size: 14px;
  line-height: 22px;
  white-space: normal;
}

.field-value {
  display: inline-flex;
  min-width: 0;
  max-width: 100%;
  align-items: center;
}

.field-value-text {
  display: inline-block;
  min-width: 0;
  max-width: 100%;
  overflow-wrap: anywhere;
  color: var(--el-text-color-primary);
  font-size: 14px;
  line-height: 22px;
  white-space: normal;
}

.field-value-text.empty {
  color: var(--el-text-color-secondary);
}

.parameter-row .field-label,
.parameter-row .field-value {
  min-height: 48px;
  align-items: center;
  border-right: 1px solid var(--el-border-color-light);
  padding: 0 12px;
}

.parameter-row .field-label {
  color: var(--el-text-color-secondary);
  font-family: ui-monospace, SFMono-Regular, Consolas, 'Liberation Mono', monospace;
  font-size: 14px;
}

.parameter-row .field-value-text {
  font-size: 14px;
}

.copy-button {
  width: 100%;
  height: 48px;
  border-radius: 0;
  color: var(--el-text-color-secondary);
}

.copy-button:hover,
.copy-button:focus-visible {
  color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}

.geometry-link-list {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.geometry-link {
  display: inline-flex;
  min-width: 0;
  max-width: 100%;
  align-items: center;
  gap: 5px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 6px;
  background: var(--el-fill-color-lighter);
  color: var(--el-text-color-primary);
  padding: 4px 7px;
}

.geometry-link:hover:not(:disabled) {
  border-color: var(--el-color-primary-light-5);
  color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}

.geometry-link:disabled {
  cursor: default;
  opacity: 0.85;
}

.geometry-link span,
.geometry-link strong {
  min-width: 0;
  overflow: hidden;
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.geometry-link span {
  color: var(--el-text-color-secondary);
}

.action-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.action-grid :deep(.el-button) {
  min-width: 0;
  margin: 0;
}

.advanced-v2 {
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  background: var(--el-bg-color-overlay);
  padding: 0 10px 10px;
}

.advanced-v2 :deep(.el-collapse-item__header) {
  min-height: 38px;
  background: transparent;
  color: var(--el-text-color-primary);
  font-size: 13px;
}

.advanced-v2 :deep(.el-collapse-item__content) {
  padding-bottom: 0;
}

.compact-empty {
  border: 1px dashed var(--el-border-color-light);
  border-radius: 7px;
  background: var(--el-fill-color-lighter);
  color: var(--el-text-color-secondary);
  font-size: 14px;
  line-height: 20px;
  padding: 12px;
  text-align: center;
}

.geometry-empty {
  color: var(--el-text-color-secondary);
  font-size: 15px;
  line-height: 22px;
  padding: 0 0 0 38px;
}

@media (max-width: 460px) {
  .object-detail-header {
    min-height: 56px;
    padding-left: 14px;
  }

  .object-detail-header strong {
    font-size: 19px;
  }

  .object-detail-body {
    padding: 10px;
  }

  .object-summary-card {
    grid-template-columns: 52px minmax(0, 1fr);
    gap: 8px 12px;
    padding: 16px 14px;
  }

  .summary-icon {
    width: 44px;
    height: 44px;
    font-size: 28px;
  }

  .summary-copy strong {
    font-size: 19px;
  }

  .section-heading {
    min-height: 48px;
    padding: 0 14px;
  }

  .section-title {
    font-size: 16px;
  }

  .section-content {
    padding: 8px 14px 10px;
  }

  .field-row {
    grid-template-columns: minmax(104px, 38%) minmax(0, 1fr);
  }

  .parameter-row {
    grid-template-columns: minmax(120px, 40%) minmax(0, 1fr) 34px;
  }
}
</style>
