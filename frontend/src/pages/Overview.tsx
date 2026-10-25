import { Link, useNavigate } from "react-router-dom";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useApi } from "../lib/api";
import { inr } from "../lib/format";
import { Card, Loading, Page } from "../ui";

type O = { kpis: Record<string, number>; history: { month: string; lakh: number }[]; breakdown: { name: string; lakh: number }[]; alerts: { level: string; text: string; to: string }[] };
const dot: Record<string, string> = { red: "bg-red-500", yellow: "bg-yellow-500", green: "bg-green-500" };

export default function Overview() {
  const { data, error } = useApi<O>("/overview"); const nav = useNavigate();
  if (!data) return <Loading error={error} />;
  const k = data.kpis;
  return (
    <Page title="Good morning, Vivek" sub="Here's what changed across your software stack.">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card onClick={() => nav("/savings")}><p className="text-xs text-stone-500">Potential savings</p><p className="text-2xl font-semibold text-green-600">{inr(k.savings)}<span className="text-xs text-stone-500">/mo</span></p><p className="mt-2 text-sm font-medium text-blue-600">View opportunities</p></Card>
        <Card onClick={() => nav("/apps")}><p className="text-xs text-stone-500">Total SaaS spend</p><p className="text-2xl font-semibold">{inr(k.spend)}<span className="text-xs text-stone-500">/mo</span></p><p className="text-sm text-yellow-600">+{k.spend_delta}% vs last month</p></Card>
        <Card><p className="text-xs text-stone-500">Active applications</p><p className="text-2xl font-semibold">{k.apps}</p><p className="text-sm text-green-600">+2 this month</p></Card>
        <Card><p className="text-xs text-stone-500">Upcoming renewals</p><p className="text-2xl font-semibold">{k.renewals}</p><p className="text-sm text-stone-500">Next in {k.next_renewal_days} days</p></Card>
      </div>
      <Card className="mt-4"><p className="mb-3 text-sm font-medium">Spend overview <span className="text-stone-500">· ₹ lakh / month</span></p>
        <ResponsiveContainer width="100%" height={240}><AreaChart data={data.history}><defs><linearGradient id="a" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#2563eb" stopOpacity={0.2} /><stop offset="1" stopColor="#2563eb" stopOpacity={0} /></linearGradient></defs>
          <CartesianGrid strokeDasharray="3 4" vertical={false} stroke="#a8a29e44" /><XAxis dataKey="month" tickLine={false} axisLine={false} fontSize={12} /><YAxis tickLine={false} axisLine={false} fontSize={12} width={32} /><Tooltip /><Area dataKey="lakh" stroke="#2563eb" strokeWidth={2} fill="url(#a)" /></AreaChart></ResponsiveContainer></Card>
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Card><p className="mb-3 text-sm font-medium">Where your money goes</p><ResponsiveContainer width="100%" height={260}><BarChart data={data.breakdown} layout="vertical"><XAxis type="number" hide /><YAxis dataKey="name" type="category" tickLine={false} axisLine={false} fontSize={12} width={96} /><Tooltip formatter={(v: number) => `₹${v}L`} /><Bar dataKey="lakh" fill="#2563eb" radius={4} barSize={12} /></BarChart></ResponsiveContainer></Card>
        <Card className="p-2"><p className="px-3 pb-1 pt-3 text-sm font-medium">Recent alerts</p>{data.alerts.map(a => <Link key={a.text} to={a.to} className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm hover:bg-stone-100 dark:hover:bg-stone-800"><span className={`size-2 rounded-full ${dot[a.level]}`} />{a.text}</Link>)}</Card>
      </div>
    </Page>
  );
}
