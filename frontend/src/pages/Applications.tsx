import { FormEvent, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { App, AppInput, requestApi, useApi } from "../lib/api";
import { formatDate, inr, lakh } from "../lib/format";
import { Badge, Card, Loading, Page, riskTone } from "../ui";

type ApplicationForm = {
  name: string;
  category: string;
  cost: string;
  licenses: string;
  active: string;
  risk: App["risk"];
  renewal: string;
};

const inputClass =
  "mt-1 w-full rounded-lg border border-stone-200 bg-white px-3 py-2 text-sm outline-none focus:border-blue-500 dark:border-stone-800 dark:bg-stone-900";

function dateInputValue(renewal: string) {
  if (/^\d{4}-\d{2}-\d{2}$/.test(renewal)) return renewal;
  const parsed = new Date(`${renewal} ${new Date().getFullYear()}`);
  if (Number.isNaN(parsed.getTime())) return "";
  const today = new Date();
  if (parsed < new Date(today.getFullYear(), today.getMonth(), today.getDate())) {
    parsed.setFullYear(parsed.getFullYear() + 1);
  }
  return `${parsed.getFullYear()}-${String(parsed.getMonth() + 1).padStart(2, "0")}-${String(parsed.getDate()).padStart(2, "0")}`;
}

export default function Applications() {
  const { data, error, loading, reload } = useApi<App[]>("/apps");
  const nav = useNavigate();
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<[keyof App, number]>(["cost", -1]);
  const [form, setForm] = useState<ApplicationForm | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState("");
  const [notice, setNotice] = useState("");
  const rows = useMemo(
    () => (data ?? [])
      .filter((app) => (app.name + app.category).toLowerCase().includes(q.toLowerCase()))
      .sort((a, b) => {
        const left = a[sort[0]];
        const right = b[sort[0]];
        return (left > right ? 1 : left < right ? -1 : 0) * sort[1];
      }),
    [data, q, sort],
  );
  if (!data) return <Page title="Applications" sub="Every software product your organization uses."><Loading error={error} loading={loading} retry={reload} /></Page>;

  const openCreate = () => {
    setEditing(null);
    setForm({ name: "", category: "", cost: "", licenses: "1", active: "0", risk: "Low", renewal: "" });
    setActionError("");
    setNotice("");
  };
  const openEdit = (app: App) => {
    setEditing(app.name);
    setForm({
      name: app.name,
      category: app.category,
      cost: String(app.cost),
      licenses: String(app.licenses),
      active: String(app.active),
      risk: app.risk,
      renewal: dateInputValue(app.renewal),
    });
    setActionError("");
    setNotice("");
  };
  const closeForm = () => {
    if (busy) return;
    setForm(null);
    setEditing(null);
  };
  const submitForm = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!form) return;
    setBusy(true);
    setActionError("");
    setNotice("");
    const input: AppInput = {
      name: form.name,
      category: form.category,
      cost: Number(form.cost),
      licenses: Number(form.licenses),
      active: Number(form.active),
      risk: form.risk,
      renewal: form.renewal,
    };
    try {
      if (editing) {
        await requestApi<App>(`/apps/${encodeURIComponent(editing)}`, { method: "PUT", body: JSON.stringify(input) });
        setNotice(`${input.name} was updated.`);
      } else {
        await requestApi<App>("/apps", { method: "POST", body: JSON.stringify(input) });
        setNotice(`${input.name} was added.`);
      }
      setForm(null);
      setEditing(null);
      reload();
    } catch (cause) {
      setActionError(cause instanceof Error ? cause.message : "Could not save this application.");
    } finally {
      setBusy(false);
    }
  };
  const deleteApp = async (app: App) => {
    if (!window.confirm(`Delete ${app.name}? This cannot be undone.`)) return;
    setBusy(true);
    setActionError("");
    setNotice("");
    try {
      await requestApi<void>(`/apps/${encodeURIComponent(app.name)}`, { method: "DELETE" });
      setNotice(`${app.name} was deleted.`);
      reload();
    } catch (cause) {
      setActionError(cause instanceof Error ? cause.message : "Could not delete this application.");
    } finally {
      setBusy(false);
    }
  };
  const th = (key: keyof App, label: string) => (
    <th
      className="cursor-pointer whitespace-nowrap px-4 py-2.5 text-left text-xs font-medium text-stone-500"
      onClick={() => setSort([key, sort[0] === key ? -sort[1] : -1])}
    >
      {label}{sort[0] === key ? (sort[1] < 0 ? " ↓" : " ↑") : ""}
    </th>
  );
  return (
    <Page
      title="Applications"
      sub="Every software product your organization uses."
      action={<button type="button" onClick={openCreate} className="rounded-lg bg-stone-900 px-3.5 py-2 text-sm font-medium text-white hover:opacity-85 dark:bg-white dark:text-stone-900">Add application</button>}
    >
      {notice && <p role="status" className="mb-3 rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-800 dark:border-green-900 dark:bg-green-950 dark:text-green-200">{notice}</p>}
      {actionError && <p role="alert" className="mb-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300">{actionError}</p>}
      {error && <div className="mb-3 flex items-center justify-between rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300"><span>Could not refresh applications.</span><button onClick={reload} className="underline">Retry</button></div>}
      {form && (
        <Card className="mb-4">
          <h2 className="mb-4 text-base font-semibold">{editing ? "Edit application" : "Add application"}</h2>
          <form onSubmit={submitForm}>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              <label className="text-xs text-stone-500">Application name<input required maxLength={100} value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} className={inputClass} /></label>
              <label className="text-xs text-stone-500">Category<input required maxLength={100} value={form.category} onChange={(event) => setForm({ ...form, category: event.target.value })} className={inputClass} /></label>
              <label className="text-xs text-stone-500">Monthly cost (INR)<input required type="number" min="0" step="1" value={form.cost} onChange={(event) => setForm({ ...form, cost: event.target.value })} className={inputClass} /></label>
              <label className="text-xs text-stone-500">Purchased licenses<input required type="number" min="1" step="1" value={form.licenses} onChange={(event) => setForm({ ...form, licenses: event.target.value })} className={inputClass} /></label>
              <label className="text-xs text-stone-500">Active licenses<input required type="number" min="0" step="1" value={form.active} onChange={(event) => setForm({ ...form, active: event.target.value })} className={inputClass} /></label>
              <label className="text-xs text-stone-500">Risk<select value={form.risk} onChange={(event) => setForm({ ...form, risk: event.target.value as App["risk"] })} className={inputClass}><option>Low</option><option>Medium</option><option>High</option></select></label>
              <label className="text-xs text-stone-500">Renewal date<input required type="date" value={form.renewal} onChange={(event) => setForm({ ...form, renewal: event.target.value })} className={inputClass} /></label>
            </div>
            <div className="mt-4 flex gap-2">
              <button disabled={busy} type="submit" className="rounded-lg bg-stone-900 px-3 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-stone-900">{busy ? "Saving…" : editing ? "Save changes" : "Add application"}</button>
              <button disabled={busy} type="button" onClick={closeForm} className="rounded-lg border border-stone-200 px-3 py-2 text-sm dark:border-stone-700">Cancel</button>
            </div>
          </form>
        </Card>
      )}
      <input value={q} onChange={(event) => setQ(event.target.value)} placeholder="Search applications" className="mb-4 w-72 rounded-lg border border-stone-200 bg-white px-3 py-2 text-sm outline-none focus:border-blue-500 dark:border-stone-800 dark:bg-stone-900" />
      <Card className="overflow-x-auto p-0">
        <table className="w-full min-w-[1050px] text-sm"><thead className="bg-stone-50 dark:bg-stone-800/50"><tr>{th("name", "Application")}{th("category", "Category")}{th("cost", "Monthly cost")}{th("licenses", "Licenses")}{th("active", "Active")}{th("utilization", "Utilization")}<th className="px-4 text-left text-xs font-medium text-stone-500">Risk</th><th className="px-4 text-left text-xs font-medium text-stone-500">Renewal</th><th className="px-4 text-left text-xs font-medium text-stone-500">Actions</th></tr></thead>
          <tbody>{rows.map((app) => <tr key={app.name} className="border-t border-stone-100 transition hover:bg-stone-50 dark:border-stone-800 dark:hover:bg-stone-800/50"><td className="px-4 py-3 font-medium">{app.name}</td><td className="px-4">{app.category}</td><td className="px-4">{inr(app.cost)}</td><td className="px-4">{app.licenses}</td><td className="px-4">{app.active}</td><td className="px-4">{app.utilization}%</td><td className="px-4"><Badge tone={riskTone[app.risk]}>{app.risk}</Badge></td><td className="px-4">{formatDate(app.renewal)}</td><td className="px-4"><div className="flex items-center gap-2"><button type="button" onClick={() => nav(`/apps/${encodeURIComponent(app.name)}`)} className="text-xs text-blue-600 hover:underline dark:text-blue-400">View</button><button type="button" onClick={() => openEdit(app)} className="text-xs hover:underline">Edit</button><button type="button" disabled={busy} onClick={() => deleteApp(app)} className="text-xs text-red-600 hover:underline disabled:opacity-50 dark:text-red-400">Delete</button></div></td></tr>)}</tbody>
        </table>
        {!rows.length && <div className="p-12 text-center text-stone-500"><p className="font-medium text-stone-900 dark:text-stone-50">{data.length ? `No applications match “${q}”` : "No applications yet."}</p>{q ? <button className="mt-3 rounded-lg border px-3 py-1.5 text-sm" onClick={() => setQ("")}>Clear search</button> : !data.length && <button className="mt-3 rounded-lg border px-3 py-1.5 text-sm" onClick={openCreate}>Add your first application</button>}</div>}
      </Card>
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
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">{m("Current spend", inr(a.cost) + "/mo")}{m("Contract value", inr(a.annual), "Annual")}{m("Utilization", a.utilization + "%", `${a.idle} idle seats`)}{m("Potential savings", inr(a.savings) + "/mo")}{m("Renewal", formatDate(a.renewal), `Risk: ${a.risk}`)}</div>
      <div className="mt-4 grid gap-4 lg:grid-cols-[1.7fr_1fr]">
        <Card><p className="mb-3 text-sm font-medium">Spend, last 12 months</p><ResponsiveContainer width="100%" height={220}><AreaChart data={a.history}><XAxis dataKey="month" tickLine={false} axisLine={false} fontSize={12} /><YAxis tickFormatter={lakh} tickLine={false} axisLine={false} fontSize={12} width={52} /><Tooltip formatter={(v: number) => inr(v)} /><Area dataKey="cost" stroke="#2563eb" strokeWidth={2} fill="#2563eb22" /></AreaChart></ResponsiveContainer></Card>
        <Card className={a.utilization < 75 ? "border-green-500 bg-green-50 dark:bg-green-950" : ""}><p className="text-xs text-stone-500">Recommended action</p><p className="text-lg font-semibold">{a.recommendation.title}</p><p className="my-2 text-sm text-stone-600 dark:text-stone-300">{a.recommendation.text}</p>{a.utilization < 75 && <p className="text-2xl font-semibold text-green-600">{inr(a.savings)}<span className="text-xs text-stone-500">/mo</span></p>}</Card>
      </div>
    </Page>
  );
}
