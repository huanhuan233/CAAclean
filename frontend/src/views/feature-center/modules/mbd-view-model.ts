import type { MbdAnnotationRecord, MbdNodeRecord } from '@/service/api/cad';

const TYPE_NAMES: Record<string, string> = {
  dimension: '尺寸',
  gdt: '形位公差',
  gdt_nonsemantic: '非语义形位公差',
  roughness: '表面粗糙度',
  datum: '基准',
  datum_simple: '基准',
  datum_system: '基准体系',
  text: '文本注解',
  flag_note: '旗标注释',
  noa: 'NOA 注释'
};

const FIELD_NAMES: Record<string, string> = {
  nominal_value: '标称值', lower_limit: '下极限', upper_limit: '上极限',
  limit_type_raw: '极限类型（原始枚举）', linear_subtype_raw: '线性尺寸类型（原始枚举）',
  precision_raw: '显示精度（原始值）', tolerance_value: '公差值',
  datum_label: '基准标识', flag_text: '旗标文本', noa_type: 'NOA 类型'
};

export function mbdTypeName(kind: string): string {
  return TYPE_NAMES[kind] || '未分类标注';
}

export function mbdFieldName(key: string): string {
  const roughness = /^field_([1-9])$/.exec(key);
  if (roughness) return `粗糙度原始字段 ${roughness[1]}`;
  const url = /^external_url_(\d+)$/.exec(key);
  if (url) return `外部引用 ${Number(url[1]) + 1}`;
  const ttrs = /^ttrs_(\d+)_nature_raw$/.exec(key);
  if (ttrs) return `TTRS ${Number(ttrs[1]) + 1} 原始类型`;
  return FIELD_NAMES[key] || key;
}

export function mbdReadStatus(value: string): { label: string; tone: 'success' | 'warning' | 'info' | 'danger' } {
  if (value === 'available' || value === 'success') return { label: '已读取', tone: 'success' };
  if (value === 'partial') return { label: '部分读取', tone: 'warning' };
  if (value === 'interface_only') return { label: '仅接口可用', tone: 'warning' };
  if (value === 'empty') return { label: '原生空值', tone: 'warning' };
  if (value === 'failed' || value === 'exception') return { label: '读取失败', tone: 'danger' };
  if (value === 'unavailable') return { label: '不可读取', tone: 'info' };
  return { label: value === 'unsupported' ? '接口不支持' : '未读取', tone: 'info' };
}

export function mbdAnnotationTitle(record: MbdAnnotationRecord): string {
  const alias = String(mbdSemanticValue(record, 'native_alias') || '').trim();
  if (alias) return alias;
  const text = String(record.annotation_text || '').trim().split(/\r?\n/, 1)[0]?.trim();
  if (text) return text;
  return `${mbdTypeName(record.component_kind)} · ${record.fta_semantic_id}`;
}

export function mbdSemanticValue(record: MbdAnnotationRecord, key: string): unknown {
  return record[key] ?? record.semantic_payload?.[key];
}

export function mbdNodeTitle(record: MbdNodeRecord): string {
  const alias = String(record.alias || '').trim();
  if (alias) return alias;
  if (record.pmi_kind === 'fta_set') return `标注集 · ${record.pmi_id}`;
  if (record.pmi_kind === 'fta_view') return `视图 · ${record.pmi_id}`;
  if (record.pmi_kind === 'fta_capture') return `捕获 · ${record.pmi_id}`;
  return record.pmi_id;
}

export function mbdNodeKindName(kind: string): string {
  return ({ fta_set: '标注集', fta_view: '视图', fta_capture: '捕获' } as Record<string, string>)[kind] || '未分类层级对象';
}

export function mbdSafeExternalUrl(value: string): string | null {
  try {
    const url = new URL(value);
    return ['https:', 'http:'].includes(url.protocol) ? url.href : null;
  } catch { return null; }
}
