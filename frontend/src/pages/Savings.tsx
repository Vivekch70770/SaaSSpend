import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Opp, useApi } from "../lib/api";
import { inr } from "../lib/format";
import { Card, Loading, Page } from "../ui";

type S = { monthly: number; annual: number; spend: number; waste: { name: string; monthly: number }[]; opportunities: Opp[] };
const colors = ["bg-green-500", "bg-blue-500", "bg-yellow-500", "bg-stone-400"];

export default function Savings() {
  const { data, error } = useApi<S>("/savings"); const nav = useNavigate(); const [open, setOpen] = useState(0);
  if (!data) return <Loading error={error} />;
  const total = data.waste.reduce((s, w) => s + w.monthly, 0);
  return (
    <Page title="Potential savings" sub="Estimated savings based on current usage.">
      <Card className="grid gap-8 p-7 md:grid-cols-2">
        <div><p className="text-xs text-stone-500">You're overpaying by</p><p className="text-5xl font-semibold tracking-tighter text-green-600">{inr(data.monthly)}<span className="text-base text-stone-500">/month</span></p>
          <p className="mb-4 mt-1 text-sm text-stone-500">{Math.round((data.monthly / data.spend) * 100)}% of your {inr(data.spend)} monthly spend · {inr(data.annual)} a year</p>
          <button className="rounded-lg bg-stone-900 px-3.5 py-2 text-sm font-medium text-white hover:opacity-85 dark:bg-white dark:text-stone-900" onClick={() => nav("/apps/Figma")}>Start with Figma: save {inr(data.opportunities[0].monthly)}/mo</button></div>
        <div><p className="mb-2 text-xs text-stone-500">Where the waste comes from</p>
          <div className="flex h-3 gap-0.5 overflow-hidden rounded-full">{data.waste.map((w, i) => <div key={w.name} className={colors[i]} style={{ flex: w.monthly }} />)}</div>
          {data.waste.map((w, i) => <div key={w.name} className="flex items-center gap-2 py-1.5 text-sm"><span className={`size-2 rounded-full ${colors[i]}`} /><span className="flex-1">{w.name}</span><b>{inr(w.monthly)}</b><span className="w-9 text-right text-xs text-stone-500">{Math.round((w.monthly / total) * 100)}%</span></div>)}</div>
      </Card>
      <h2 className="mb-3 mt-8 text-sm font-medium text-stone-500">Top opportunities</h2>
      <div className="grid gap-3">{data.opportunities.map((o, i) => {
        const n = o.confidence === "High" ? 3 : 2;
        return <Card key={o.app} onClick={() => setOpen(open === i ? -1 : i)} className={open === i ? "border-stone-900 dark:border-stone-300" : ""}>
          <div className="flex items-center gap-4"><div className="flex-1"><p className="font-medium">{o.type}</p><p className="text-xs text-stone-500">{o.app}</p></div>
            <div className="text-right"><p className="text-lg font-semibold text-green-600">{inr(o.monthly)}<span className="text-xs text-stone-500">/mo</span></p>
              <span className="mr-1 inline-flex gap-0.5 align-middle">{[1, 2, 3].map(k => <i key={k} className={`h-1 w-3.5 rounded ${k <= n ? (n === 3 ? "bg-green-500" : "bg-yellow-500") : "bg-stone-200 dark:bg-stone-700"}`} />)}</span><span className="text-xs text-stone-500">{o.confidence} confidence</span></div></div>
          {open === i && <div className="mt-4 border-t border-stone-200 pt-4 dark:border-stone-800"><p className="text-xs text-stone-500">Why we calculated this</p><p className="mb-3 mt-1 text-sm">{o.why}</p>
            <p className="text-xs text-stone-500">{o.active} of {o.licenses} seats active ({o.utilization}%)</p><div className="my-2 h-1.5 overflow-hidden rounded-full bg-stone-100 dark:bg-stone-800"><div className="h-full bg-blue-500" style={{ width: `${o.utilization}%` }} /></div>
            <p className="text-xs text-stone-500">Annual impact {inr(o.annual)}</p>
            <button className="mt-3 rounded-lg border border-stone-200 px-3 py-1.5 text-sm hover:bg-stone-100 dark:border-stone-800 dark:hover:bg-stone-800" onClick={e => { e.stopPropagation(); nav(`/apps/${o.app.split(" + ")[0]}`); }}>Open {o.app.split(" + ")[0]}</button></div>}
        </Card>;
      })}</div>
    </Page>
  );
}
