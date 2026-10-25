import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Opp, useApi } from "../lib/api";
import { inr } from "../lib/format";
import { Card, Loading, Page } from "../ui";

type SavingsData = {
  monthly: number;
  estimated_monthly: number;
  annual: number;
  spend: number;
  realized_monthly: number;
  estimate_basis: string;
  waste: { name: string; monthly: number }[];
  opportunities: Opp[];
};

export default function Savings() {
  const { data, error, loading, reload } = useApi<SavingsData>("/savings");
  const nav = useNavigate();
  const [open, setOpen] = useState(0);
  if (!data) return <Page title="Potential savings" sub="Estimated savings based on current usage."><Loading error={error} loading={loading} retry={reload} /></Page>;
  const total = data.waste.reduce((s, w) => s + w.monthly, 0);
  return (
    <Page title="Potential savings" sub="Estimated opportunities based on purchased and active licenses. These are not realized savings.">
      <Card className="grid gap-8 p-7 md:grid-cols-2">
        <div>
          <p className="text-xs text-stone-500">Estimated potential savings</p>
          <p className="text-5xl font-semibold tracking-tighter text-green-600">{inr(data.estimated_monthly)}<span className="text-base text-stone-500">/month</span></p>
          <p className="mb-4 mt-1 text-sm text-stone-500">{data.spend > 0 ? `${Math.round((data.estimated_monthly / data.spend) * 100)}% of` : "Against"} {inr(data.spend)} monthly spend · {inr(data.annual)} annualized</p>
          <p className="text-sm text-stone-500">Realized savings: {inr(data.realized_monthly)}/month</p>
          {data.opportunities[0] && <button className="mt-4 rounded-lg bg-stone-900 px-3.5 py-2 text-sm font-medium text-white hover:opacity-85 dark:bg-white dark:text-stone-900" onClick={() => nav(`/apps/${encodeURIComponent(data.opportunities[0].app)}`)}>Review {data.opportunities[0].app}</button>}
        </div>
        <div>
          <p className="mb-2 text-xs text-stone-500">Potential by category</p>
          {total > 0 && <div className="flex h-3 gap-0.5 overflow-hidden rounded-full">{data.waste.map((w) => <div key={w.name} className="bg-green-500" style={{ flex: w.monthly }} />)}</div>}
          {data.waste.map((w) => <div key={w.name} className="flex items-center gap-2 py-1.5 text-sm"><span className="size-2 rounded-full bg-green-500" /><span className="flex-1">{w.name}</span><b>{inr(w.monthly)}</b><span className="w-9 text-right text-xs text-stone-500">{total ? `${Math.round((w.monthly / total) * 100)}%` : "0%"}</span></div>)}
          {!data.waste.length && <p className="py-4 text-sm text-stone-500">No unused-license savings are currently identified.</p>}
        </div>
      </Card>
      <p className="mt-3 text-xs leading-5 text-stone-500">{data.estimate_basis}</p>
      <h2 className="mb-3 mt-8 text-sm font-medium text-stone-500">Top opportunities</h2>
      <div className="grid gap-3">{data.opportunities.length === 0 ? <Card className="text-sm text-stone-500">No applications currently have unused licenses.</Card> : data.opportunities.map((o, i) => {
        return <Card key={o.app} onClick={() => setOpen(open === i ? -1 : i)} className={open === i ? "border-stone-900 dark:border-stone-300" : ""}>
          <div className="flex items-center gap-4"><div className="flex-1"><p className="font-medium">{o.type}</p><p className="text-xs text-stone-500">{o.app}</p></div>
            <div className="text-right"><p className="text-lg font-semibold text-green-600">{inr(o.monthly)}<span className="text-xs text-stone-500">/mo</span></p>
              <span className="text-xs text-stone-500">Estimated potential</span></div></div>
          {open === i && <div className="mt-4 border-t border-stone-200 pt-4 dark:border-stone-800"><p className="text-xs text-stone-500">Why we calculated this</p><p className="mb-3 mt-1 text-sm">{o.why}</p>
            <p className="text-xs text-stone-500">{o.active} of {o.licenses} seats active, {o.unused} unused ({o.utilization}% utilization)</p><div className="my-2 h-1.5 overflow-hidden rounded-full bg-stone-100 dark:bg-stone-800"><div className="h-full bg-blue-500" style={{ width: `${o.utilization}%` }} /></div>
            <p className="text-xs text-stone-500">Potential annual impact {inr(o.annual)} · not yet realized</p>
            <button className="mt-3 rounded-lg border border-stone-200 px-3 py-1.5 text-sm hover:bg-stone-100 dark:border-stone-800 dark:hover:bg-stone-800" onClick={event => { event.stopPropagation(); nav(`/apps/${encodeURIComponent(o.app)}`); }}>Open {o.app}</button></div>}
        </Card>;
      })}</div>
    </Page>
  );
}
