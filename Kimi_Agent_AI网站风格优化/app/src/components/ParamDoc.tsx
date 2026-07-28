
import type { ParamDocRow } from '@/types';

export function paramDocToMarkdown(rows: ParamDocRow[], title: string, prompt?: string): string {
  const lines = [
    `# ${title}`,
    '',
    prompt ? `> 生成描述：${prompt}` : '',
    prompt ? '' : '',
    '| 附图标记 | 构件名称 | 图元编码 | 关键参数 | 材料 | 装配关系 |',
    '| --- | --- | --- | --- | --- | --- |',
    ...rows.map((r) => `| ${r.refNo} | ${r.name} | ${r.code} | ${r.keyParams} | ${r.material} | ${r.relation} |`),
    '',
    '—— 由专利附图智能生成系统输出 · 符合《专利审查指南》附图规范',
  ];
  return lines.join('\n');
}

export function downloadText(filename: string, content: string) {
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}

export default function ParamDoc({ rows, compact }: { rows: ParamDocRow[]; compact?: boolean }) {
  return (
    <div className="overflow-auto rounded-lg border border-slate-200">
      <table className={`w-full text-left ${compact ? 'text-xs' : 'text-sm'}`}>
        <thead>
          <tr className="bg-slate-100 text-slate-600">
            <th className="px-3 py-2 font-medium whitespace-nowrap">附图标记</th>
            <th className="px-3 py-2 font-medium whitespace-nowrap">构件名称</th>
            <th className="px-3 py-2 font-medium whitespace-nowrap">图元编码</th>
            <th className="px-3 py-2 font-medium">关键参数</th>
            <th className="px-3 py-2 font-medium whitespace-nowrap">材料</th>
            <th className="px-3 py-2 font-medium">装配关系</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.refNo} className="border-t border-slate-200 text-slate-600 hover:bg-slate-50">
              <td className="px-3 py-2">
                <span className="inline-flex h-5 w-5 items-center justify-center rounded-full border border-slate-500 text-xs">{r.refNo}</span>
              </td>
              <td className="px-3 py-2 whitespace-nowrap text-slate-800">{r.name}</td>
              <td className="px-3 py-2 whitespace-nowrap font-mono text-violet-700">{r.code}</td>
              <td className="px-3 py-2 text-slate-500">{r.keyParams}</td>
              <td className="px-3 py-2 whitespace-nowrap text-slate-500">{r.material}</td>
              <td className="px-3 py-2 text-slate-500">{r.relation}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
