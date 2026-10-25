import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  Activity,
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  CalendarDays,
  Check,
  CircleDollarSign,
  Layers3,
  Sparkles,
  UsersRound,
} from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { requestApi, useApi } from "../lib/api";
import { formatDate, inr, lakh } from "../lib/format";
import { Card, Loading, Page } from "../ui";

type OverviewData = {
  kpis: {
    spend: number;
    spend_delta: number;
    savings: number;
    apps: number;
    renewals: number;
    next_renewal_days: number | null;
  };
  history: { month: string; lakh: number }[];
  breakdown: { name: string; lakh: number }[];
  alerts: { level: string; text: string; to: string }[];
};
type AppItem = { name: string; cost: number; utilization: number };
type LicenseData = {
  summary: { purchased: number; assigned: number; unused: number; utilization: number };
};
type RenewalData = {
  items: {
    name: string;
    renewal_date: string | null;
    days_remaining: number | null;
    annual_cost: number;
    urgency: string;
    renewal_status: string;
    status: string;
  }[];
};

const rangeOptions = ["6M", "12M"] as const;
const alertDot: Record<string, string> = {
  red: "bg-rose-400",
  yellow: "bg-amber-300",
  green: "bg-[#c6f36a]",
};
const bars = ["#c6f36a", "#8fba55", "#697b4e", "#566046", "#43483d", "#33372f"];

function ChartTip({ active, payload, label }: { active?: boolean; payload?: { value?: number }[]; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="chart-tip">
      <p className="text-[11px] text-stone-400">{label}</p>
      <p className="mt-1 font-semibold text-white">₹{Number(payload[0].value ?? 0).toFixed(1)}L</p>
    </div>
  );
}

function MiniLoading() {
  return <div className="flex h-32 items-center justify-center text-sm text-stone-500">Loading data…</div>;
}

export default function Overview() {
  const { data, error, loading, reload } = useApi<OverviewData>("/overview");
  const { data: apps, error: appsError, reload: reloadApps } = useApi<AppItem[]>("/apps");
  const { data: licenses, error: licensesError, reload: reloadLicenses } = useApi<LicenseData>("/licenses");
  const { data: renewals, error: renewalsError, reload: reloadRenewals } = useApi<RenewalData>("/renewals");
  const [range, setRange] = useState<(typeof rangeOptions)[number]>("12M");
  const [reviewing, setReviewing] = useState<string | null>(null);
  const [reviewError, setReviewError] = useState("");
  const navigate = useNavigate();

  const history = useMemo(
    () => (data?.history ?? []).slice(range === "6M" ? -6 : undefined),
    [data, range],
  );
  const leaders = useMemo(
    () => [...(data?.breakdown ?? [])]
      .sort((a, b) => b.lakh - a.lakh)
      .slice(0, 6),
    [data],
  );
  const upcoming = useMemo(
    () => [...(renewals?.items ?? [])]
      .sort((a, b) => (a.days_remaining ?? Number.MAX_SAFE_INTEGER) - (b.days_remaining ?? Number.MAX_SAFE_INTEGER))
      .slice(0, 4),
    [renewals],
  );

  if (!data) {
    return (
      <Page title="Overview" sub="Your software spend, at a glance.">
        <Loading error={error} loading={loading} retry={reload} />
      </Page>
    );
  }

  const k = data.kpis;
  const licenseSummary = licenses?.summary;
  const utilization = licenseSummary?.utilization ?? 0;
  const reviewRenewal = async (name: string) => {
    setReviewing(name);
    setReviewError("");
    try {
      await requestApi(`/renewals/${encodeURIComponent(name)}/review`, { method: "POST" });
      reloadRenewals();
    } catch (failure) {
      setReviewError(failure instanceof Error ? failure.message : "Could not review this renewal.");
    } finally {
      setReviewing(null);
    }
  };

  return (
    <Page
      title="Overview"
      sub="A clear view of your software spend, usage, and what needs attention."
      action={
        <div className="hidden items-center gap-2 rounded-full border border-white/[.08] bg-white/[.035] px-3.5 py-2 text-xs text-stone-300 sm:flex">
          <span className="size-1.5 rounded-full bg-[#c6f36a] shadow-[0_0_9px_#c6f36a]" />
          All systems operational
        </div>
      }
    >
      <div className="overview-grid">
        <Card className="spend-card col-span-12 lg:col-span-8">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 text-sm text-stone-400">
                <span className="grid size-8 place-items-center rounded-xl bg-[#c6f36a]/10 text-[#c6f36a]">
                  <CircleDollarSign size={17} />
                </span>
                Total SaaS spend
              </div>
              <div className="mt-5 flex flex-wrap items-end gap-x-3 gap-y-1">
                <p className="metric-value">{lakh(k.spend)}</p>
                <span className="mb-1.5 text-sm text-stone-500">per month</span>
              </div>
              <div className="mt-2 flex items-center gap-1.5 text-xs">
                <span className="inline-flex items-center gap-1 rounded-full bg-rose-400/10 px-2 py-1 font-medium text-rose-300">
                  <ArrowUpRight size={13} /> {k.spend_delta}%
                </span>
                <span className="text-stone-500">compared to last month</span>
              </div>
            </div>
            <div className="flex rounded-xl border border-white/[.08] bg-black/20 p-1">
              {rangeOptions.map((option) => (
                <button
                  key={option}
                  type="button"
                  aria-pressed={range === option}
                  className={`range-button ${range === option ? "range-button-active" : ""}`}
                  onClick={() => setRange(option)}
                >
                  {option}
                </button>
              ))}
            </div>
          </div>
          <div className="mt-6 h-[220px] w-full sm:h-[255px]">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={history} margin={{ top: 8, right: 8, bottom: 0, left: -14 }}>
                <defs>
                  <linearGradient id="spend-fill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#c6f36a" stopOpacity={0.22} />
                    <stop offset="92%" stopColor="#c6f36a" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="rgba(255,255,255,.055)" vertical={false} />
                <XAxis dataKey="month" axisLine={false} tickLine={false} tick={{ fill: "#777a70", fontSize: 11 }} dy={10} />
                <YAxis
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: "#777a70", fontSize: 11 }}
                  tickFormatter={(value: number) => `₹${value}L`}
                  width={46}
                />
                <Tooltip content={<ChartTip />} cursor={{ stroke: "rgba(198,243,106,.2)", strokeDasharray: "4 4" }} />
                <Area
                  type="monotone"
                  dataKey="lakh"
                  stroke="#c6f36a"
                  strokeWidth={2.5}
                  fill="url(#spend-fill)"
                  activeDot={{ r: 5, fill: "#c6f36a", stroke: "#10120e", strokeWidth: 3 }}
                  animationDuration={850}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-2 flex items-center justify-between border-t border-white/[.06] pt-3 text-xs text-stone-500">
            <span>Monthly spend · INR</span>
            <span>{history.length} month trend</span>
          </div>
        </Card>

        <Card className="savings-card col-span-12 lg:col-span-4">
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-2 text-sm text-stone-300">
              <span className="grid size-8 place-items-center rounded-xl bg-[#c6f36a]/10 text-[#c6f36a]">
                <Sparkles size={16} />
              </span>
              Savings opportunity
            </span>
            <span className="rounded-full border border-[#c6f36a]/20 bg-[#c6f36a]/[.08] px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[.12em] text-[#c6f36a]">
              Ready to act
            </span>
          </div>
          <p className="mt-8 text-[11px] font-medium uppercase tracking-[.16em] text-stone-500">Potential monthly savings</p>
          <p className="mt-1 text-[clamp(2rem,4vw,3.1rem)] font-semibold leading-tight tracking-[-.06em] text-[#d5f891]">
            {lakh(k.savings)}
          </p>
          <p className="mt-2 text-sm leading-6 text-stone-400">
            Find unused seats and right-size subscriptions across your stack.
          </p>
          <div className="mt-6 rounded-2xl border border-[#c6f36a]/10 bg-[#c6f36a]/[.045] p-4">
            <p className="text-xs text-stone-400">Annual opportunity</p>
            <p className="mt-1 text-sm font-medium text-stone-200">{inr(k.savings * 12)}</p>
          </div>
          <Link to="/savings" className="action-link mt-5">
            Explore savings <ArrowRight size={15} />
          </Link>
        </Card>

        <Card className="stat-card col-span-6 lg:col-span-3">
          <div className="flex items-center justify-between text-stone-400">
            <span className="text-xs">Active applications</span>
            <Layers3 size={16} className="text-stone-500" />
          </div>
          <p className="mt-3 text-3xl font-semibold tracking-tight text-stone-100">{k.apps}</p>
          <p className="mt-2 text-xs text-stone-500">Across your software stack</p>
        </Card>
        <Card className="stat-card col-span-6 lg:col-span-3">
          <div className="flex items-center justify-between text-stone-400">
            <span className="text-xs">Assigned seats</span>
            <UsersRound size={16} className="text-stone-500" />
          </div>
          <p className="mt-3 text-3xl font-semibold tracking-tight text-stone-100">
            {licenseSummary ? `${licenseSummary.assigned}` : "—"}
          </p>
          <p className="mt-2 text-xs text-stone-500">
            {licenseSummary ? `${licenseSummary.unused} unused licenses` : "License data unavailable"}
          </p>
        </Card>
        <Card className="stat-card col-span-6 lg:col-span-3">
          <div className="flex items-center justify-between text-stone-400">
            <span className="text-xs">License utilization</span>
            <Activity size={16} className="text-stone-500" />
          </div>
          <p className="mt-3 text-3xl font-semibold tracking-tight text-stone-100">
            {licenseSummary ? `${utilization}%` : "—"}
          </p>
          <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/[.07]">
            <div
              className="h-full rounded-full bg-[#c6f36a] transition-[width] duration-700"
              style={{ width: `${utilization}%` }}
            />
          </div>
        </Card>
        <Card className="stat-card col-span-6 lg:col-span-3">
          <div className="flex items-center justify-between text-stone-400">
            <span className="text-xs">Upcoming renewals</span>
            <CalendarDays size={16} className="text-stone-500" />
          </div>
          <p className="mt-3 text-3xl font-semibold tracking-tight text-stone-100">{k.renewals}</p>
          <p className="mt-2 text-xs text-stone-500">{k.next_renewal_days === null ? "No scheduled renewals" : k.next_renewal_days === 0 ? "Due today" : k.next_renewal_days < 0 ? `${Math.abs(k.next_renewal_days)} days overdue` : `Next in ${k.next_renewal_days} days`}</p>
        </Card>

        <Card className="col-span-12 lg:col-span-7">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="section-title">Application spend</h2>
              <p className="mt-1 text-xs text-stone-500">Monthly spend by application · top 6</p>
            </div>
            <Link to="/apps" className="subtle-link">View all <ArrowUpRight size={13} /></Link>
          </div>
          <div className="mt-6 space-y-[18px]">
            {leaders.map((item, index) => {
              const max = leaders[0]?.lakh ?? 1;
              return (
                <button
                  key={item.name}
                  type="button"
                  className="group w-full text-left"
                  onClick={() => navigate(item.name === "Other" ? "/apps" : `/apps/${encodeURIComponent(item.name)}`)}
                >
                  <span className="mb-2 flex items-center justify-between gap-3 text-xs">
                    <span className="truncate text-stone-300 transition group-hover:text-white">
                      {item.name === "Other" ? "Other applications" : item.name}
                    </span>
                    <span className="shrink-0 font-medium tabular-nums text-stone-200">₹{item.lakh.toFixed(1)}L</span>
                  </span>
                  <span className="block h-[7px] overflow-hidden rounded-full bg-white/[.06]">
                    <span
                      className="block h-full rounded-full transition-[width] duration-700"
                      style={{ width: `${Math.max(5, (item.lakh / max) * 100)}%`, backgroundColor: bars[index] }}
                    />
                  </span>
                </button>
              );
            })}
          </div>
          {appsError && <p className="mt-4 text-xs text-amber-300">Application details are unavailable right now.</p>}
          {apps && <p className="mt-5 border-t border-white/[.06] pt-3 text-xs text-stone-500">{apps.length} tracked applications</p>}
        </Card>

        <Card className="col-span-12 lg:col-span-5">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="section-title">License health</h2>
              <p className="mt-1 text-xs text-stone-500">Purchased seats in active use</p>
            </div>
            <Link to="/licenses" className="subtle-link">Details <ArrowUpRight size={13} /></Link>
          </div>
          {licenses ? (
            <>
              <div className="mt-6 flex items-center gap-5">
                <div className="relative grid size-[104px] shrink-0 place-items-center rounded-full" style={{ background: `conic-gradient(#c6f36a ${utilization}%, rgba(255,255,255,.08) ${utilization}% 100%)` }}>
                  <div className="grid size-[82px] place-items-center rounded-full bg-[#111310] text-center">
                    <div>
                      <p className="text-2xl font-semibold tracking-tight text-[#d5f891]">{utilization}%</p>
                      <p className="text-[9px] uppercase tracking-[.12em] text-stone-500">in use</p>
                    </div>
                  </div>
                </div>
                <div className="min-w-0 flex-1 space-y-3">
                  <div className="flex justify-between gap-3 text-xs">
                    <span className="text-stone-400">Assigned seats</span>
                    <span className="font-medium text-stone-200">{licenseSummary?.assigned.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between gap-3 text-xs">
                    <span className="text-stone-400">Purchased</span>
                    <span className="font-medium text-stone-200">{licenseSummary?.purchased.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between gap-3 border-t border-white/[.06] pt-3 text-xs">
                    <span className="text-stone-400">Unused seats</span>
                    <span className="font-medium text-[#d5f891]">{licenseSummary?.unused.toLocaleString()}</span>
                  </div>
                </div>
              </div>
              <div className="mt-6 flex items-center justify-between gap-3 rounded-xl border border-white/[.06] bg-white/[.025] px-3.5 py-3 text-xs leading-5">
                <span className="text-stone-400">Unused seats by application</span>
                <Link to="/licenses" className="shrink-0 font-medium text-[#c6f36a] hover:text-[#e0ffa0]">Review <ArrowRight size={12} className="ml-1 inline" /></Link>
              </div>
            </>
          ) : licensesError ? (
            <div className="mt-6 rounded-xl border border-rose-400/15 bg-rose-400/[.05] p-4 text-sm text-rose-200">
              License utilization could not be loaded.
              <button className="ml-2 underline underline-offset-2" onClick={reloadLicenses}>Retry</button>
            </div>
          ) : <MiniLoading />}
        </Card>

        <Card className="col-span-12 lg:col-span-7">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="section-title">Upcoming renewals</h2>
              <p className="mt-1 text-xs text-stone-500">Plan ahead for your next contract dates</p>
            </div>
            <Link to="/renewals" className="subtle-link">All renewals <ArrowUpRight size={13} /></Link>
          </div>
          {renewalsError ? (
            <div className="mt-6 rounded-xl border border-rose-400/15 bg-rose-400/[.05] p-4 text-sm text-rose-200">
              Renewal data could not be loaded.
              <button className="ml-2 underline underline-offset-2" onClick={reloadRenewals}>Retry</button>
            </div>
          ) : renewals ? (
            <>
            {reviewError && <p role="alert" className="mt-4 rounded-lg border border-rose-400/15 bg-rose-400/[.05] px-3 py-2 text-xs text-rose-200">{reviewError}</p>}
            <div className="mt-4 divide-y divide-white/[.055]">
              {upcoming.map((item) => {
                const done = item.status === "Reviewed";
                const isReviewing = reviewing === item.name;
                return (
                  <div key={item.name} className="flex flex-wrap items-center gap-3 py-3.5">
                    <div className="grid size-9 shrink-0 place-items-center rounded-xl border border-white/[.07] bg-white/[.035] text-xs font-semibold text-stone-300">
                      {item.name.slice(0, 2).toUpperCase()}
                    </div>
                    <div className="min-w-[120px] flex-1">
                      <p className="text-sm font-medium text-stone-200">{item.name}</p>
                      <p className="mt-0.5 text-[11px] text-stone-500">
                        {item.renewal_date ? formatDate(item.renewal_date) : "Date unavailable"}
                        {" · "}{item.days_remaining === null
                          ? "Days unavailable"
                          : item.days_remaining < 0
                            ? `${Math.abs(item.days_remaining)} days overdue`
                            : item.days_remaining === 0 ? "Today" : `In ${item.days_remaining} days`}
                        {" · "}{item.renewal_status}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-xs font-medium text-stone-200">{inr(item.annual_cost)}</p>
                      <p className="mt-0.5 text-[10px] text-stone-500">annual</p>
                    </div>
                    <button
                      type="button"
                      title={done ? "Renewal reviewed" : "Mark renewal reviewed"}
                      aria-label={`${done ? "Reviewed" : "Review"} ${item.name} renewal`}
                      disabled={done || isReviewing}
                      onClick={() => reviewRenewal(item.name)}
                      className={`ml-1 grid size-8 place-items-center rounded-lg border transition disabled:cursor-wait ${done ? "border-[#c6f36a]/20 bg-[#c6f36a]/10 text-[#c6f36a]" : "border-white/[.08] text-stone-500 hover:border-[#c6f36a]/30 hover:text-[#c6f36a]"}`}
                    >
                      {done ? <Check size={14} /> : isReviewing ? <span className="size-3 animate-spin rounded-full border border-stone-500 border-t-[#c6f36a]" /> : <ArrowRight size={14} />}
                    </button>
                  </div>
                );
              })}
              {!upcoming.length && <p className="py-8 text-center text-sm text-stone-500">No upcoming renewals.</p>}
            </div>
            </>
          ) : <MiniLoading />}
        </Card>

        <Card className="col-span-12 lg:col-span-5">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="section-title">Needs your attention</h2>
              <p className="mt-1 text-xs text-stone-500">A few things to take a closer look at</p>
            </div>
            <span className="grid size-8 place-items-center rounded-xl bg-white/[.04] text-stone-400"><Activity size={15} /></span>
          </div>
          <div className="mt-4 space-y-1">
            {data.alerts.slice(0, 4).map((alert) => (
              <Link key={alert.text} to={alert.to} className="alert-row">
                <span className={`mt-1.5 size-1.5 shrink-0 rounded-full ${alertDot[alert.level] ?? "bg-stone-500"}`} />
                <span className="min-w-0 flex-1 text-xs leading-5 text-stone-300">{alert.text}</span>
                {alert.level === "red"
                  ? <ArrowDownRight size={14} className="shrink-0 text-rose-300" />
                  : <ArrowRight size={14} className="shrink-0 text-stone-600 transition group-hover:text-[#c6f36a]" />}
              </Link>
            ))}
          </div>
        </Card>
      </div>
    </Page>
  );
}
