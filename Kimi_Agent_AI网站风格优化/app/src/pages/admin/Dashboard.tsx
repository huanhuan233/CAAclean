import { useMemo } from 'react';
import { BarChart3, Coins, TrendingUp, Activity, PieChart as PieIcon } from 'lucide-react';
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  AreaChart, Area, PieChart, Pie, Cell,
} from 'recharts';
import { useStore } from '@/store/AppStore';

const NODES = ['数据解析', '向量化', '文生图', '图改图', '参数文档'] as const;
const COLORS: Record<string, string> = {
  数据解析: '#8b5cf6', 向量化: '#34d399', 文生图: '#818cf8', 图改图: '#fbbf24', 参数文档: '#f472b6',
};
const fmt = (n: number) => (n >= 10000 ? (n / 10000).toFixed(1) + 'w' : n.toLocaleString());

const tooltipStyle = {
  contentStyle: { background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: 8, fontSize: 12 },
  labelStyle: { color: '#64748b' },
  itemStyle: { color: '#334155' },
} as const;

export default function Dashboard() {
  const { tokenLogs } = useStore();

  const totals = useMemo(() => {
    const t: Record<string, number> = {};
    NODES.forEach((n) => (t[n] = tokenLogs.reduce((s, d) => s + d[n], 0)));
    return t;
  }, [tokenLogs]);
  const grandTotal = Object.values(totals).reduce((a, b) => a + b, 0);
  const today = tokenLogs[tokenLogs.length - 1];
  const todayTotal = NODES.reduce((s, n) => s + today[n], 0);
  const pieData = NODES.map((n) => ({ name: n, value: totals[n] }));

  return (
    <div className="p-6">
      <header className="mb-5">
        <h1 className="text-lg font-semibold text-slate-800">数据看板</h1>
        <p className="mt-0.5 text-xs text-slate-500">各节点 Token 消耗量与总体消耗量（近 7 日）</p>
      </header>

      {/* 汇总卡片 */}
      <div className="mb-5 grid grid-cols-2 gap-3 xl:grid-cols-4">
        <div className="rounded-xl border border-slate-200 bg-gradient-to-br from-violet-600/15 to-transparent p-4">
          <div className="flex items-center gap-2 text-[11px] text-slate-500"><Coins className="h-3.5 w-3.5 text-violet-600" />总消耗量（7日）</div>
          <div className="mt-2 font-mono text-2xl font-bold text-violet-700">{grandTotal.toLocaleString()}</div>
          <div className="mt-1 text-[10px] text-slate-500">tokens · 约 ¥{(grandTotal * 0.00002).toFixed(2)}</div>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <div className="flex items-center gap-2 text-[11px] text-slate-500"><Activity className="h-3.5 w-3.5 text-emerald-600" />今日消耗</div>
          <div className="mt-2 font-mono text-2xl font-bold text-emerald-600">{todayTotal.toLocaleString()}</div>
          <div className="mt-1 text-[10px] text-slate-500">{today.date} · 5 个节点</div>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <div className="flex items-center gap-2 text-[11px] text-slate-500"><TrendingUp className="h-3.5 w-3.5 text-indigo-500" />消耗最高节点</div>
          <div className="mt-2 text-2xl font-bold text-indigo-600">文生图</div>
          <div className="mt-1 font-mono text-[10px] text-slate-500">{fmt(totals['文生图'])} tok · 占比 {((totals['文生图'] / grandTotal) * 100).toFixed(0)}%</div>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <div className="flex items-center gap-2 text-[11px] text-slate-500"><BarChart3 className="h-3.5 w-3.5 text-amber-600" />日均消耗</div>
          <div className="mt-2 font-mono text-2xl font-bold text-amber-700">{fmt(Math.round(grandTotal / tokenLogs.length))}</div>
          <div className="mt-1 text-[10px] text-slate-500">tokens / 日</div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
        {/* 堆叠柱状图 */}
        <section className="rounded-xl border border-slate-200 bg-white p-4 xl:col-span-2">
          <h2 className="mb-3 text-sm font-semibold text-slate-700">各节点每日 Token 消耗（堆叠）</h2>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={tokenLogs} margin={{ top: 4, right: 8, left: -12, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 11 }} axisLine={{ stroke: '#cbd5e1' }} />
                <YAxis tick={{ fill: '#64748b', fontSize: 11 }} axisLine={{ stroke: '#cbd5e1' }} tickFormatter={fmt} />
                <Tooltip {...tooltipStyle} />
                <Legend wrapperStyle={{ fontSize: 11, color: '#94a3b8' }} />
                {NODES.map((n) => (
                  <Bar key={n} dataKey={n} stackId="a" fill={COLORS[n]} radius={n === '参数文档' ? [3, 3, 0, 0] : 0} />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>

        {/* 占比饼图 */}
        <section className="rounded-xl border border-slate-200 bg-white p-4">
          <h2 className="mb-1 flex items-center gap-1.5 text-sm font-semibold text-slate-700"><PieIcon className="h-4 w-4 text-slate-500" />节点消耗占比</h2>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={pieData} dataKey="value" nameKey="name" innerRadius={48} outerRadius={78} paddingAngle={3} strokeWidth={0}>
                  {pieData.map((d) => <Cell key={d.name} fill={COLORS[d.name]} />)}
                </Pie>
                <Tooltip {...tooltipStyle} formatter={(v: number) => v.toLocaleString() + ' tok'} />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="space-y-1">
            {NODES.map((n) => (
              <div key={n} className="flex items-center gap-2 text-[11px]">
                <span className="h-2 w-2 rounded-sm" style={{ background: COLORS[n] }} />
                <span className="text-slate-500">{n}</span>
                <span className="ml-auto font-mono text-slate-600">{fmt(totals[n])}</span>
                <span className="w-9 text-right font-mono text-slate-500">{((totals[n] / grandTotal) * 100).toFixed(0)}%</span>
              </div>
            ))}
          </div>
        </section>

        {/* 总量趋势 */}
        <section className="rounded-xl border border-slate-200 bg-white p-4 xl:col-span-3">
          <h2 className="mb-3 text-sm font-semibold text-slate-700">总体消耗趋势</h2>
          <div className="h-52">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={tokenLogs.map((d) => ({ date: d.date, 总消耗: NODES.reduce((s, n) => s + d[n], 0) }))} margin={{ top: 4, right: 12, left: -8, bottom: 0 }}>
                <defs>
                  <linearGradient id="total" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.3} />
                    <stop offset="100%" stopColor="#8b5cf6" stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 11 }} axisLine={{ stroke: '#cbd5e1' }} />
                <YAxis tick={{ fill: '#64748b', fontSize: 11 }} axisLine={{ stroke: '#cbd5e1' }} tickFormatter={fmt} />
                <Tooltip {...tooltipStyle} formatter={(v: number) => v.toLocaleString() + ' tok'} />
                <Area type="monotone" dataKey="总消耗" stroke="#8b5cf6" strokeWidth={2} fill="url(#total)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </section>
      </div>
    </div>
  );
}
