import { useMemo, useState } from "react";
import { ArrowDownRight, ArrowUpRight, Download, TrendingUp } from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { App, useApi } from "../lib/api";
import { inr, lakh } from "../lib/format";
import { Card, Loading, Page } from "../ui";

type OverviewData = {
  kpis: { spend: number; spend_delta: number; savings: number };
  history: { month: string; lakh: number }[];
};

const tip = ({ active, payload, label }: { active?: boolean; payload?: { value?: number; name?: string }[]; label?: string }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="chart-tip">
      <p className="text-[11px] text-stone-400">{label}</p>
      <p className="mt-1 font-semibold text-white">
        {payload[0].name === "utilization" ? `${payload[0].value}%` : `₹${Number(payload[0].value ?? 0).toFixed(1)}L`}
      </p>
    </div>
  );
};

export default function Reports() {
  const { data, error, loading, reload } = useApi<OverviewData>("/overview");
  const { data: apps, error: appsError, reload: reloadApps } = useApi<App[]>("/apps");
  const [range, setRange] = useState<6 | 12>(12);
  const history = useMemo(() => (data?.history ?? []).slice(-range), [data, range]);
  const utilization = useMemo(
    () => [...(apps ?? [])].sort((a, b) => a.utilization - b.utilization).slice(0, 8),
    [apps],
  );

  if (!data) {
    return (
      <Page title="Reports" sub="Spending trends, savings, and license utilization.">
        <Loading error={error} loading={loading} retry={reload} />
      </Page>
    );
  }

  const exportReport = () => {
    if (!apps) return;
    const rows = [
      ["Application", "Category", "Monthly spend (INR)", "Purchased seats", "Assigned seats", "Utilization (%)"],
      ...apps.map((app) => [app.name, app.category, app.cost, app.licenses, app.active, app.utilization]),
    ];
    const csv = rows.map((row) => row.map((value) => `"${String(value).replace(/"/g, '""')}"`).join(",")).join("\r\n");
    const href = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const anchor = document.createElement("a");
    anchor.href = href;
    anchor.download = "saasspend-report.csv";
    anchor.click();
    URL.revokeObjectURL(href);
  };

  return (
    <Page
      title="Reports"
      sub="Spending trends, savings, and license utilization from your SaaSSpend workspace."
      action={
        <button
          type="button"
          onClick={exportReport}
          disabled={!apps}
          className="inline-flex items-center gap-2 rounded-xl border border-white/[.09] bg-white/[.035] px-3.5 py-2.5 text-xs font-medium text-stone-300 transition hover:border-[#c6f36a]/25 hover:text-[#d5f891] disabled:cursor-wait disabled:opacity-50"
        >
          <Download size={14} /> Export CSV
        </button>
      }
    >
      <div className="grid gap-3 sm:grid-cols-3">
        <Card className="stat-card">
          <p className="text-xs text-stone-500">Current monthly spend</p>
          <p className="mt-3 text-2xl font-semibold tracking-tight text-stone-100">{lakh(data.kpis.spend)}</p>
          <p className="mt-2 inline-flex items-center gap-1 text-xs text-rose-300">
            <ArrowUpRight size={13} /> {data.kpis.spend_delta}% vs last month
          </p>
        </Card>
        <Card className="stat-card">
          <p className="text-xs text-stone-500">Savings identified</p>
          <p className="mt-3 text-2xl font-semibold tracking-tight text-[#d5f891]">{lakh(data.kpis.savings)}</p>
          <p className="mt-2 text-xs text-stone-500">Potential, per month</p>
        </Card>
        <Card className="stat-card">
          <p className="text-xs text-stone-500">Applications tracked</p>
          <p className="mt-3 text-2xl font-semibold tracking-tight text-stone-100">{apps?.length ?? "—"}</p>
          <p className="mt-2 text-xs text-stone-500">Connected to the current API dataset</p>
        </Card>
      </div>

      <Card className="mt-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="section-title">Spend trend</h2>
            <p className="mt-1 text-xs text-stone-500">Month-over-month software spend</p>
          </div>
          <div className="flex rounded-xl border border-white/[.08] bg-black/20 p-1">
            {([6, 12] as const).map((months) => (
              <button
                key={months}
                type="button"
                aria-pressed={range === months}
                onClick={() => setRange(months)}
                className={`range-button ${range === months ? "range-button-active" : ""}`}
              >
                {months} months
              </button>
            ))}
          </div>
        </div>
        <div className="mt-5 h-[270px]">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={history} margin={{ top: 8, right: 8, bottom: 0, left: -14 }}>
              <defs>
                <linearGradient id="report-spend-fill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#c6f36a" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="#c6f36a" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="rgba(255,255,255,.055)" vertical={false} />
              <XAxis dataKey="month" axisLine={false} tickLine={false} tick={{ fill: "#777a70", fontSize: 11 }} dy={10} />
              <YAxis axisLine={false} tickLine={false} tick={{ fill: "#777a70", fontSize: 11 }} tickFormatter={(value: number) => `₹${value}L`} width={46} />
              <Tooltip content={tip} cursor={{ stroke: "rgba(198,243,106,.2)", strokeDasharray: "4 4" }} />
              <Area dataKey="lakh" name="spend" type="monotone" stroke="#c6f36a" strokeWidth={2.5} fill="url(#report-spend-fill)" animationDuration={750} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
        <div className="flex items-center justify-between border-t border-white/[.06] pt-3 text-xs text-stone-500">
          <span>Source: SaaSSpend spend history</span>
          <span>{history.length} data points</span>
        </div>
      </Card>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Card>
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="section-title">Lowest utilization</h2>
              <p className="mt-1 text-xs text-stone-500">Applications with seats to review</p>
            </div>
            <TrendingUp size={16} className="text-stone-500" />
          </div>
          {appsError ? (
            <div className="mt-6 rounded-xl border border-rose-400/15 bg-rose-400/[.05] p-4 text-sm text-rose-200">
              Application data could not be loaded.
              <button className="ml-2 underline underline-offset-2" onClick={reloadApps}>Retry</button>
            </div>
          ) : apps ? (
            <div className="mt-6 h-[230px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={utilization} layout="vertical" margin={{ top: 0, right: 10, bottom: 0, left: 6 }}>
                  <CartesianGrid stroke="rgba(255,255,255,.045)" horizontal={false} />
                  <XAxis type="number" domain={[0, 100]} axisLine={false} tickLine={false} tick={{ fill: "#777a70", fontSize: 10 }} tickFormatter={(value: number) => `${value}%`} />
                  <YAxis dataKey="name" type="category" axisLine={false} tickLine={false} tick={{ fill: "#b6b8ae", fontSize: 11 }} width={105} />
                  <Tooltip content={tip} cursor={{ fill: "rgba(255,255,255,.025)" }} />
                  <Bar dataKey="utilization" name="utilization" fill="#c6f36a" radius={[0, 5, 5, 0]} barSize={11} animationDuration={700} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : <p className="py-12 text-center text-sm text-stone-500">Loading application utilization…</p>}
          <p className="mt-3 border-t border-white/[.06] pt-3 text-xs text-stone-500">
            Low utilization can indicate an opportunity to reclaim seats.
          </p>
        </Card>
        <Card>
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="section-title">Savings outlook</h2>
              <p className="mt-1 text-xs text-stone-500">Projected impact at the current opportunity level</p>
            </div>
            <ArrowDownRight size={16} className="text-[#c6f36a]" />
          </div>
          <p className="mt-7 text-xs uppercase tracking-[.13em] text-stone-500">Annualized opportunity</p>
          <p className="mt-2 text-4xl font-semibold tracking-[-.055em] text-[#d5f891]">{inr(data.kpis.savings * 12)}</p>
          <div className="mt-7 space-y-4">
            {[["Monthly opportunity", inr(data.kpis.savings)], ["Current monthly spend", inr(data.kpis.spend)]].map(([label, value]) => (
              <div key={label} className="flex items-center justify-between gap-4 border-t border-white/[.06] pt-3 text-xs">
                <span className="text-stone-400">{label}</span>
                <span className="font-medium text-stone-200">{value}</span>
              </div>
            ))}
          </div>
          <p className="mt-5 rounded-xl border border-white/[.06] bg-white/[.025] p-3 text-xs leading-5 text-stone-500">
            Estimates are based on the existing SaaSSpend API dataset and are not additional live vendor quotes.
          </p>
        </Card>
      </div>
    </Page>
  );
}
