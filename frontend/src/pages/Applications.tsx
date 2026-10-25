import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { App, useApi } from "../lib/api";
import { inr, lakh } from "../lib/format";
import { Badge, Card, Loading, Page, riskTone } from "../ui";

export default function Applications() {
  const { data, error } = useApi<App[]>("/apps"); const nav = useNavigate();
  const [q, setQ] = useState(""); const [sort, setSort] = useState<[keyof App, number]>(["cost", -1]);
  const rows = useMemo(() => (data ?? []).filter(a => (a.name + a.category).toLowerCase().includes(q.toLowerCase())).sort((a, b) => (a[sort[0]] > b[sort[0]] ? 1 : -1) * sort[1]), [data, q, sort]);
  if (!data) return <Loading error={error} />;
  const th = (k: keyof App, l: string) => <th className="cursor-pointer px-4 py-2.5 text-left text-xs font-medium text-stone-500" onClick={() => setSort([k, sort[0] === k ? -sort[1] : -1])}>{l}{sort[0] === k ? (sort[1] < 0 ? " ↓" : " ↑") : ""}</th>;
  return (
    <Page title="Applications" sub="Every software product your organization uses.">
      <input value={q} onChange={e => setQ(e.target.value)} placeholder="Search applications" className="mb-4 w-72 rounded-lg border border-stone-200 bg-white px-3 py-2 text-sm outline-none focus:border-blue-500 dark:border-stone-800 dark:bg-stone-900" />
      <Card className="overflow-x-auto p-0"><table className="w-full text-sm"><thead className="bg-stone-50 dark:bg-stone-800/50"><tr>{th("name", "Application")}{th("category", "Category")}{th("cost", "Monthly cost")}{th("licenses", "Licenses")}{th("active", "Active")}{th("utilization", "Utilization")}<th className="px-4 text-left text-xs font-medium text-stone-500">Risk</th><th className="px-4 text-left text-xs font-medium text-stone-500">Renewal</th></tr></thead>
        <tbody>{rows.map(a => <tr key={a.name} onClick={() => nav(`/apps/${a.name}`)} className="cursor-pointer border-t border-stone-100 transition hover:bg-stone-50 dark:border-stone-800 dark:hover:bg-stone-800/50"><td className="px-4 py-3 font-medium">{a.name}</td><td className="px-4">{a.category}</td><td className="px-4">{inr(a.cost)}</td><td className="px-4">{a.licenses}</td><td className="px-4">{a.active}</td><td className="px-4">{a.utilization}%</td><td className="px-4"><Badge tone={riskTone[a.risk]}>{a.risk}</Badge></td><td className="px-4">{a.renewal}</td></tr>)}</tbody></table>
        {!rows.length && <div className="p-12 text-center text-stone-500"><p className="font-medium text-stone-900 dark:text-stone-50">No applications match “{q}”</p><button className="mt-3 rounded-lg border px-3 py-1.5 text-sm" onClick={() => setQ("")}>Clear search</button></div>}</Card>
    </Page>
  );
}

type D = App & { history: { month: string; cost: number }[]; recommendation: { title: string; text: string } };
export function AppDetail() {
  const { name } = useParams(); const { data: a, error } = useApi<D>(`/apps/${name}`);
  if (!a) return <Loading error={error} />;
  const m = (l: string, v: string, s = "") => <Card><p className="text-xs text-stone-500">{l}</p><p className="text-xl font-semibold">{v}</p><p className="text-xs text-stone-500">{s}</p></Card>;
  return (
    <Page title={a.name} sub={a.category}>
      <p className="-mt-4 mb-4 text-xs text-stone-500"><Link to="/apps" className="hover:underline">Applications</Link> / {a.name}</p>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">{m("Current spend", inr(a.cost) + "/mo")}{m("Contract value", inr(a.annual), "Annual")}{m("Utilization", a.utilization + "%", `${a.idle} idle seats`)}{m("Potential savings", inr(a.savings) + "/mo")}{m("Renewal", a.renewal, `Risk: ${a.risk}`)}</div>
      <div className="mt-4 grid gap-4 lg:grid-cols-[1.7fr_1fr]">
        <Card><p className="mb-3 text-sm font-medium">Spend, last 12 months</p><ResponsiveContainer width="100%" height={220}><AreaChart data={a.history}><XAxis dataKey="month" tickLine={false} axisLine={false} fontSize={12} /><YAxis tickFormatter={lakh} tickLine={false} axisLine={false} fontSize={12} width={52} /><Tooltip formatter={(v: number) => inr(v)} /><Area dataKey="cost" stroke="#2563eb" strokeWidth={2} fill="#2563eb22" /></AreaChart></ResponsiveContainer></Card>
        <Card className={a.utilization < 75 ? "border-green-500 bg-green-50 dark:bg-green-950" : ""}><p className="text-xs text-stone-500">Recommended action</p><p className="text-lg font-semibold">{a.recommendation.title}</p><p className="my-2 text-sm text-stone-600 dark:text-stone-300">{a.recommendation.text}</p>{a.utilization < 75 && <p className="text-2xl font-semibold text-green-600">{inr(a.savings)}<span className="text-xs text-stone-500">/mo</span></p>}</Card>
      </div>
    </Page>
  );
}
