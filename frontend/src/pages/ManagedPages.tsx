import { useMemo, useState } from "react";
import { Badge, Card, Loading, Page } from "../ui";
import { requestApi, useApi } from "../lib/api";
import { formatDate, inr } from "../lib/format";

type License = {
  name: string;
  category: string;
  purchased: number;
  assigned: number;
  unused: number;
  utilization: number;
  cost: number;
};
type LicenseResponse = {
  summary: { purchased: number; assigned: number; unused: number; utilization: number };
  items: License[];
};
type Renewal = {
  name: string;
  category: string;
  renewal_date: string | null;
  days_remaining: number | null;
  monthly_cost: number;
  annual_cost: number;
  risk: string;
  urgency: "Overdue" | "High" | "Medium" | "Low" | "Unknown";
  renewal_status: "Overdue" | "Due soon" | "Upcoming" | "Unknown";
  status: string;
};
type RenewalResponse = {
  summary: { upcoming: number; due_soon: number; overdue: number; annual_cost: number };
  items: Renewal[];
};
type ShadowApp = {
  id: string;
  name: string;
  category: string;
  monthly_cost: number;
  risk: "High" | "Medium" | "Low";
  discovered: string;
  owner: string;
  status: "Pending review" | "Approved" | "Dismissed";
};
type ShadowResponse = {
  summary: { discovered: number; pending: number; monthly_spend: number };
  items: ShadowApp[];
};
type AccessUser = {
  id: string;
  name: string;
  email: string;
  department: string;
  last_active: string;
  active: boolean;
  reviewed: boolean;
  assignments: { app: string; role: string }[];
  assignment_count: number;
  excessive_access: boolean;
};
type AccessResponse = {
  summary: { users: number; inactive: number; excessive: number };
  items: AccessUser[];
};
type Finding = {
  id: string;
  title: string;
  severity: "High" | "Medium" | "Low";
  application: string;
  affected: string;
  recommendation: string;
  status: "Open" | "Resolved";
};
type SecurityResponse = {
  summary: { open: number; high: number };
  items: Finding[];
  simulated: boolean;
};

const controlClass =
  "rounded-lg border border-stone-200 bg-white px-3 py-2 text-sm outline-none focus:border-blue-500 dark:border-stone-800 dark:bg-stone-900";

function Metric({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return (
    <Card>
      <p className="text-xs text-stone-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold">{value}</p>
      {detail && <p className="mt-1 text-xs text-stone-500">{detail}</p>}
    </Card>
  );
}

function PrototypeNote({ children }: { children: string }) {
  return (
    <div className="mb-4 rounded-xl border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900 dark:border-blue-900 dark:bg-blue-950/50 dark:text-blue-200">
      {children}
    </div>
  );
}

function LoadState({
  loading,
  error,
  retry,
}: {
  loading: boolean;
  error: boolean;
  retry: () => void;
}) {
  if (loading) return <Loading error={false} />;
  if (!error) return null;
  return (
    <div className="rounded-xl border border-red-200 bg-red-50 p-5 text-sm text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200">
      <p>Could not load this page from the API. Confirm the backend is running and try again.</p>
      <button className="mt-3 rounded-lg border border-current px-3 py-1.5" onClick={retry}>
        Retry
      </button>
    </div>
  );
}

function ActionError({ message }: { message: string }) {
  if (!message) return null;
  return <p role="alert" className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">{message}</p>;
}

function EmptyRows({ message, clear }: { message: string; clear: () => void }) {
  return (
    <div className="p-10 text-center text-sm text-stone-500">
      <p>{message}</p>
      <button className="mt-2 rounded-lg border border-stone-200 px-3 py-1.5 hover:bg-stone-50 dark:border-stone-700 dark:hover:bg-stone-800" onClick={clear}>
        Clear filters
      </button>
    </div>
  );
}

function SortHead({
  label,
  active,
  direction,
  onClick,
}: {
  label: string;
  active: boolean;
  direction: "asc" | "desc";
  onClick: () => void;
}) {
  return (
    <th className="whitespace-nowrap px-4 py-2.5 text-left text-xs font-medium text-stone-500">
      <button className="hover:text-stone-900 dark:hover:text-white" onClick={onClick}>
        {label}{active ? (direction === "asc" ? " ↑" : " ↓") : ""}
      </button>
    </th>
  );
}

function sortValue<T>(items: T[], value: (item: T) => string | number, direction: "asc" | "desc") {
  return [...items].sort((left, right) => {
    const a = value(left);
    const b = value(right);
    const compared = typeof a === "number" && typeof b === "number"
      ? a - b
      : String(a).localeCompare(String(b));
    return compared * (direction === "asc" ? 1 : -1);
  });
}

function changeSort<T extends string>(key: T, current: T, direction: "asc" | "desc", setKey: (value: T) => void, setDirection: (value: "asc" | "desc") => void) {
  if (key === current) setDirection(direction === "asc" ? "desc" : "asc");
  else {
    setKey(key);
    setDirection("asc");
  }
}

function tableHeader(
  label: string,
  key: string,
  current: string,
  direction: "asc" | "desc",
  onSort: (key: string) => void,
) {
  return <SortHead key={key} label={label} active={current === key} direction={direction} onClick={() => onSort(key)} />;
}

export function LicensesPage() {
  const { data, error, loading, reload } = useApi<LicenseResponse>("/licenses");
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const [sort, setSort] = useState("name");
  const [direction, setDirection] = useState<"asc" | "desc">("asc");
  const [working, setWorking] = useState("");
  const [actionError, setActionError] = useState("");
  const rows = useMemo(() => {
    const filtered = (data?.items ?? []).filter((item) =>
      `${item.name} ${item.category}`.toLowerCase().includes(query.toLowerCase())
      && (filter === "all" || (filter === "unused" ? item.unused > 0 : item.utilization < 75)),
    );
    return sortValue(filtered, (item) => {
      if (sort === "purchased") return item.purchased;
      if (sort === "assigned") return item.assigned;
      if (sort === "unused") return item.unused;
      if (sort === "utilization") return item.utilization;
      return item.name;
    }, direction);
  }, [data, query, filter, sort, direction]);
  const onSort = (key: string) => changeSort(key, sort, direction, setSort, setDirection);

  async function reclaim(name: string) {
    setWorking(name);
    setActionError("");
    try {
      await requestApi<LicenseResponse>(`/licenses/${encodeURIComponent(name)}/reclaim`, { method: "POST" });
      reload();
    } catch (cause) {
      setActionError(cause instanceof Error ? cause.message : "Could not reclaim seats.");
    } finally {
      setWorking("");
    }
  }

  if (!data) return <Page title="Licenses" sub="Purchased seats, assignments, and utilization across your SaaS portfolio."><LoadState loading={loading} error={error} retry={reload} /></Page>;
  return (
    <Page title="Licenses" sub="Purchased seats, assignments, and utilization across your SaaS portfolio.">
      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Metric label="Purchased seats" value={data.summary.purchased.toLocaleString()} />
        <Metric label="Assigned seats" value={data.summary.assigned.toLocaleString()} />
        <Metric label="Unused seats" value={data.summary.unused.toLocaleString()} detail="Available to reclaim" />
        <Metric label="Overall utilization" value={`${data.summary.utilization}%`} />
      </div>
      <PrototypeNote>Seat counts and costs are prototype data from the mock provider; no live vendor license integrations are connected.</PrototypeNote>
      <ActionError message={actionError} />
      <div className="mb-3 flex flex-wrap gap-2">
        <input aria-label="Search licenses" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search applications" className={`${controlClass} min-w-48 flex-1 sm:max-w-xs`} />
        <select aria-label="Filter licenses" value={filter} onChange={(event) => setFilter(event.target.value)} className={controlClass}>
          <option value="all">All licenses</option><option value="unused">Has unused seats</option><option value="low">Under 75% utilized</option>
        </select>
      </div>
      <Card className="overflow-x-auto p-0">
        <table className="w-full min-w-[760px] text-sm">
          <thead className="bg-stone-50 dark:bg-stone-800/50"><tr>
            {tableHeader("Application", "name", sort, direction, onSort)}
            {tableHeader("Purchased", "purchased", sort, direction, onSort)}
            {tableHeader("Assigned", "assigned", sort, direction, onSort)}
            {tableHeader("Unused", "unused", sort, direction, onSort)}
            {tableHeader("Utilization", "utilization", sort, direction, onSort)}
            <th className="px-4 py-2.5 text-left text-xs font-medium text-stone-500">Monthly spend</th>
            <th className="px-4 py-2.5 text-left text-xs font-medium text-stone-500">Action</th>
          </tr></thead>
          <tbody>{rows.map((item) => <tr key={item.name} className="border-t border-stone-100 dark:border-stone-800">
            <td className="px-4 py-3"><span className="font-medium">{item.name}</span><span className="ml-2 text-xs text-stone-500">{item.category}</span></td>
            <td className="px-4">{item.purchased}</td><td className="px-4">{item.assigned}</td><td className="px-4">{item.unused}</td>
            <td className="px-4"><div className="flex items-center gap-2"><span>{item.utilization}%</span><div className="h-1.5 w-16 rounded-full bg-stone-100 dark:bg-stone-700"><div className="h-full rounded-full bg-blue-500" style={{ width: `${item.utilization}%` }} /></div></div></td>
            <td className="px-4">{inr(item.cost)}</td>
            <td className="px-4 py-2"><button disabled={!item.unused || working === item.name} onClick={() => reclaim(item.name)} className="whitespace-nowrap rounded-lg border border-stone-200 px-2.5 py-1.5 text-xs hover:bg-stone-50 disabled:cursor-not-allowed disabled:opacity-40 dark:border-stone-700 dark:hover:bg-stone-800">{working === item.name ? "Reclaiming…" : "Reclaim unused"}</button></td>
          </tr>)}</tbody>
        </table>
        {!rows.length && <EmptyRows message="No licenses match your search and filters." clear={() => { setQuery(""); setFilter("all"); }} />}
      </Card>
    </Page>
  );
}

export function RenewalsPage() {
  const { data, error, loading, reload } = useApi<RenewalResponse>("/renewals");
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const [sort, setSort] = useState("urgency");
  const [direction, setDirection] = useState<"asc" | "desc">("asc");
  const [working, setWorking] = useState("");
  const [actionError, setActionError] = useState("");
  const rows = useMemo(() => {
    const filtered = (data?.items ?? []).filter((item) =>
      `${item.name} ${item.category}`.toLowerCase().includes(query.toLowerCase())
      && (filter === "all"
        || (filter === "review" ? item.status === "Needs review"
          : filter === "upcoming" ? item.renewal_status === "Upcoming"
            : filter === "due-soon" ? item.renewal_status === "Due soon"
              : filter === "overdue" ? item.renewal_status === "Overdue"
                : item.urgency === filter)),
    );
    return sortValue(filtered, (item) => {
      if (sort === "date") return item.renewal_date ?? "9999-12-31";
      if (sort === "cost") return item.annual_cost;
      if (sort === "name") return item.name;
      return item.days_remaining ?? Number.MAX_SAFE_INTEGER;
    }, direction);
  }, [data, query, filter, sort, direction]);
  const onSort = (key: string) => changeSort(key, sort, direction, setSort, setDirection);

  async function markReviewed(name: string) {
    setWorking(name);
    setActionError("");
    try {
      await requestApi<RenewalResponse>(`/renewals/${encodeURIComponent(name)}/review`, { method: "POST" });
      reload();
    } catch (cause) {
      setActionError(cause instanceof Error ? cause.message : "Could not update renewal review.");
    } finally {
      setWorking("");
    }
  }

  if (!data) return <Page title="Renewals" sub="Upcoming contract dates, costs, and renewal priorities."><LoadState loading={loading} error={error} retry={reload} /></Page>;
  return (
    <Page title="Renewals" sub="Upcoming contract dates, costs, and renewal priorities.">
      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Metric label="Upcoming renewals" value={String(data.summary.upcoming)} />
        <Metric label="Due in 30 days" value={String(data.summary.due_soon)} detail="Prioritize contracts that are approaching" />
        <Metric label="Overdue renewals" value={String(data.summary.overdue)} detail="Past their stored renewal date" />
        <Metric label="Annual contract value" value={inr(data.summary.annual_cost)} />
      </div>
      <PrototypeNote>Renewal dates and subscription costs use saved application records. Urgent is 0–14 days, due soon is 0–30 days, upcoming is more than 30 days, and overdue dates are before today.</PrototypeNote>
      <ActionError message={actionError} />
      <div className="mb-3 flex flex-wrap gap-2">
        <input aria-label="Search renewals" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search applications" className={`${controlClass} min-w-48 flex-1 sm:max-w-xs`} />
        <select aria-label="Filter renewals" value={filter} onChange={(event) => setFilter(event.target.value)} className={controlClass}>
          <option value="all">All renewals</option><option value="upcoming">Upcoming (over 30 days)</option><option value="due-soon">Due soon (within 30 days)</option><option value="overdue">Overdue</option><option value="review">Needs review</option><option value="High">Urgent (within 14 days)</option><option value="Medium">Due soon (15–30 days)</option>
        </select>
      </div>
      <Card className="overflow-x-auto p-0">
        <table className="w-full min-w-[820px] text-sm">
          <thead className="bg-stone-50 dark:bg-stone-800/50"><tr>
            {tableHeader("Application", "name", sort, direction, onSort)}
            {tableHeader("Renewal date", "date", sort, direction, onSort)}
            {tableHeader("Days remaining", "urgency", sort, direction, onSort)}
            {tableHeader("Annual cost", "cost", sort, direction, onSort)}
            <th className="px-4 py-2.5 text-left text-xs font-medium text-stone-500">Urgency</th>
            <th className="px-4 py-2.5 text-left text-xs font-medium text-stone-500">Review</th>
            <th className="px-4 py-2.5 text-left text-xs font-medium text-stone-500">Action</th>
          </tr></thead>
          <tbody>{rows.map((item) => <tr key={item.name} className="border-t border-stone-100 dark:border-stone-800">
            <td className="px-4 py-3"><span className="font-medium">{item.name}</span><span className="ml-2 text-xs text-stone-500">{item.category}</span></td>
            <td className="px-4">{item.renewal_date ? formatDate(item.renewal_date) : "Date unavailable"}</td>
            <td className="px-4 font-medium">{item.days_remaining === null ? "Unavailable" : item.days_remaining < 0 ? `${Math.abs(item.days_remaining)} days overdue` : item.days_remaining === 0 ? "Today" : `In ${item.days_remaining} days`}</td>
            <td className="px-4">{inr(item.annual_cost)}<span className="ml-1 text-xs text-stone-500">({inr(item.monthly_cost)}/mo)</span></td>
            <td className="px-4"><Badge tone={item.urgency === "Overdue" || item.urgency === "High" ? "red" : item.urgency === "Medium" ? "yellow" : "green"}>{item.renewal_status}</Badge></td>
            <td className="px-4">{item.status}</td>
            <td className="px-4 py-2"><button disabled={item.status === "Reviewed" || working === item.name} onClick={() => markReviewed(item.name)} className="whitespace-nowrap rounded-lg border border-stone-200 px-2.5 py-1.5 text-xs hover:bg-stone-50 disabled:cursor-not-allowed disabled:opacity-40 dark:border-stone-700 dark:hover:bg-stone-800">{working === item.name ? "Saving…" : item.status === "Reviewed" ? "Reviewed" : "Mark reviewed"}</button></td>
          </tr>)}</tbody>
        </table>
        {!rows.length && <EmptyRows message="No renewals match your search and filters." clear={() => { setQuery(""); setFilter("all"); }} />}
      </Card>
    </Page>
  );
}

export function ShadowItPage() {
  const { data, error, loading, reload } = useApi<ShadowResponse>("/shadow-it");
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const [sort, setSort] = useState("monthly_cost");
  const [direction, setDirection] = useState<"asc" | "desc">("desc");
  const [working, setWorking] = useState("");
  const [actionError, setActionError] = useState("");
  const rows = useMemo(() => {
    const filtered = (data?.items ?? []).filter((item) =>
      `${item.name} ${item.category} ${item.owner}`.toLowerCase().includes(query.toLowerCase())
      && (filter === "all" || (filter === "pending" ? item.status === "Pending review" : item.risk === filter)),
    );
    return sortValue(filtered, (item) => sort === "risk" ? item.risk : sort === "name" ? item.name : item.monthly_cost, direction);
  }, [data, query, filter, sort, direction]);
  const onSort = (key: string) => changeSort(key, sort, direction, setSort, setDirection);

  async function updateStatus(item: ShadowApp, status: "Approved" | "Dismissed") {
    setWorking(item.id);
    setActionError("");
    try {
      await requestApi<ShadowResponse>(`/shadow-it/${item.id}`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      reload();
    } catch (cause) {
      setActionError(cause instanceof Error ? cause.message : "Could not update application review.");
    } finally {
      setWorking("");
    }
  }

  if (!data) return <Page title="Shadow IT" sub="Review software reported outside the approved application list."><LoadState loading={loading} error={error} retry={reload} /></Page>;
  return (
    <Page title="Shadow IT" sub="Review software reported outside the approved application list.">
      <div className="mb-4 grid gap-3 sm:grid-cols-3">
        <Metric label="Discovered applications" value={String(data.summary.discovered)} />
        <Metric label="Pending review" value={String(data.summary.pending)} />
        <Metric label="Estimated monthly spend" value={inr(data.summary.monthly_spend)} detail="Estimated, not connected billing data" />
      </div>
      <PrototypeNote>These are illustrative mock discoveries; SaaSSpend is not monitoring devices, networks, or live vendor accounts.</PrototypeNote>
      <ActionError message={actionError} />
      <div className="mb-3 flex flex-wrap gap-2">
        <input aria-label="Search discovered applications" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search applications or owners" className={`${controlClass} min-w-48 flex-1 sm:max-w-xs`} />
        <select aria-label="Filter discovered applications" value={filter} onChange={(event) => setFilter(event.target.value)} className={controlClass}>
          <option value="all">All applications</option><option value="pending">Pending review</option><option value="High">High risk</option><option value="Medium">Medium risk</option><option value="Low">Low risk</option>
        </select>
      </div>
      <Card className="overflow-x-auto p-0">
        <table className="w-full min-w-[850px] text-sm">
          <thead className="bg-stone-50 dark:bg-stone-800/50"><tr>
            {tableHeader("Application", "name", sort, direction, onSort)}
            <th className="px-4 py-2.5 text-left text-xs font-medium text-stone-500">Owner / team</th>
            {tableHeader("Estimated spend", "monthly_cost", sort, direction, onSort)}
            {tableHeader("Risk", "risk", sort, direction, onSort)}
            <th className="px-4 py-2.5 text-left text-xs font-medium text-stone-500">Discovered</th>
            <th className="px-4 py-2.5 text-left text-xs font-medium text-stone-500">Review status</th>
            <th className="px-4 py-2.5 text-left text-xs font-medium text-stone-500">Actions</th>
          </tr></thead>
          <tbody>{rows.map((item) => <tr key={item.id} className="border-t border-stone-100 dark:border-stone-800">
            <td className="px-4 py-3"><span className="font-medium">{item.name}</span><span className="ml-2 text-xs text-stone-500">{item.category}</span></td>
            <td className="px-4">{item.owner}</td><td className="px-4">{inr(item.monthly_cost)}/mo</td>
            <td className="px-4"><Badge tone={item.risk === "High" ? "red" : item.risk === "Medium" ? "yellow" : "green"}>{item.risk}</Badge></td>
            <td className="px-4">{new Date(`${item.discovered}T00:00:00`).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}</td>
            <td className="px-4">{item.status}</td>
            <td className="px-4 py-2"><div className="flex gap-2">
              <button disabled={item.status !== "Pending review" || working === item.id} onClick={() => updateStatus(item, "Approved")} className="rounded-lg border border-stone-200 px-2 py-1.5 text-xs hover:bg-stone-50 disabled:opacity-40 dark:border-stone-700 dark:hover:bg-stone-800">{working === item.id ? "Saving…" : "Approve"}</button>
              <button disabled={item.status !== "Pending review" || working === item.id} onClick={() => updateStatus(item, "Dismissed")} className="rounded-lg border border-stone-200 px-2 py-1.5 text-xs hover:bg-stone-50 disabled:opacity-40 dark:border-stone-700 dark:hover:bg-stone-800">Dismiss</button>
            </div></td>
          </tr>)}</tbody>
        </table>
        {!rows.length && <EmptyRows message="No discovered applications match your search and filters." clear={() => { setQuery(""); setFilter("all"); }} />}
      </Card>
    </Page>
  );
}

export function AccessPage() {
  const { data, error, loading, reload } = useApi<AccessResponse>("/access");
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const [sort, setSort] = useState("name");
  const [direction, setDirection] = useState<"asc" | "desc">("asc");
  const [working, setWorking] = useState("");
  const [actionError, setActionError] = useState("");
  const rows = useMemo(() => {
    const filtered = (data?.items ?? []).filter((item) =>
      `${item.name} ${item.email} ${item.department} ${item.assignments.map((assignment) => assignment.app).join(" ")}`.toLowerCase().includes(query.toLowerCase())
      && (filter === "all" || (filter === "inactive" ? !item.active : filter === "excessive" ? item.excessive_access : item.active)),
    );
    return sortValue(filtered, (item) => sort === "assignments" ? item.assignment_count : sort === "last_active" ? item.last_active : item.name, direction);
  }, [data, query, filter, sort, direction]);
  const onSort = (key: string) => changeSort(key, sort, direction, setSort, setDirection);

  async function updateUser(user: AccessUser, action: "review" | "deactivate") {
    setWorking(user.id);
    setActionError("");
    try {
      await requestApi<AccessResponse>(`/access/${user.id}/${action}`, { method: "POST" });
      reload();
    } catch (cause) {
      setActionError(cause instanceof Error ? cause.message : "Could not update user access.");
    } finally {
      setWorking("");
    }
  }

  if (!data) return <Page title="Access" sub="Review application assignments, user status, and elevated access."><LoadState loading={loading} error={error} retry={reload} /></Page>;
  return (
    <Page title="Access" sub="Review application assignments, user status, and elevated access.">
      <div className="mb-4 grid gap-3 sm:grid-cols-3">
        <Metric label="Users in directory" value={String(data.summary.users)} />
        <Metric label="Inactive users" value={String(data.summary.inactive)} detail="Accounts with assignments that may need revoking" />
        <Metric label="Excessive-access warnings" value={String(data.summary.excessive)} detail="More than one administrator assignment" />
      </div>
      <PrototypeNote>User records and application assignments are mock examples, not synced from an identity provider or SaaS directory.</PrototypeNote>
      <ActionError message={actionError} />
      <div className="mb-3 flex flex-wrap gap-2">
        <input aria-label="Search users and applications" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search users, teams, or apps" className={`${controlClass} min-w-48 flex-1 sm:max-w-xs`} />
        <select aria-label="Filter users" value={filter} onChange={(event) => setFilter(event.target.value)} className={controlClass}>
          <option value="all">All users</option><option value="active">Active</option><option value="inactive">Inactive</option><option value="excessive">Excessive access</option>
        </select>
      </div>
      <Card className="overflow-x-auto p-0">
        <table className="w-full min-w-[1000px] text-sm">
          <thead className="bg-stone-50 dark:bg-stone-800/50"><tr>
            {tableHeader("User", "name", sort, direction, onSort)}
            <th className="px-4 py-2.5 text-left text-xs font-medium text-stone-500">Status</th>
            <th className="px-4 py-2.5 text-left text-xs font-medium text-stone-500">Applications and roles</th>
            {tableHeader("Assignments", "assignments", sort, direction, onSort)}
            {tableHeader("Last active", "last_active", sort, direction, onSort)}
            <th className="px-4 py-2.5 text-left text-xs font-medium text-stone-500">Access review</th>
            <th className="px-4 py-2.5 text-left text-xs font-medium text-stone-500">Action</th>
          </tr></thead>
          <tbody>{rows.map((user) => <tr key={user.id} className="border-t border-stone-100 align-top dark:border-stone-800">
            <td className="px-4 py-3"><p className="font-medium">{user.name}</p><p className="text-xs text-stone-500">{user.email} · {user.department}</p></td>
            <td className="px-4 py-3"><Badge tone={user.active ? "green" : "red"}>{user.active ? "Active" : "Inactive"}</Badge>{user.excessive_access && <p className="mt-1"><Badge tone="yellow">Excessive access</Badge></p>}</td>
            <td className="max-w-sm px-4 py-3"><div className="flex flex-wrap gap-1.5">{user.assignments.map((assignment) => <span key={`${assignment.app}-${assignment.role}`} className="rounded-md bg-stone-100 px-2 py-1 text-xs dark:bg-stone-800">{assignment.app} · {assignment.role}</span>)}</div></td>
            <td className="px-4 py-3">{user.assignment_count}</td><td className="px-4 py-3">{user.last_active}</td>
            <td className="px-4 py-3">{user.reviewed ? <Badge tone="green">Reviewed</Badge> : <Badge tone="yellow">Needs review</Badge>}</td>
            <td className="px-4 py-3"><div className="flex flex-col items-start gap-1.5">
              <button disabled={user.reviewed || working === user.id} onClick={() => updateUser(user, "review")} className="whitespace-nowrap rounded-lg border border-stone-200 px-2.5 py-1 text-xs hover:bg-stone-50 disabled:opacity-40 dark:border-stone-700 dark:hover:bg-stone-800">{working === user.id ? "Saving…" : user.reviewed ? "Reviewed" : "Mark reviewed"}</button>
              {user.active && <button disabled={working === user.id} onClick={() => updateUser(user, "deactivate")} className="whitespace-nowrap rounded-lg border border-red-200 px-2.5 py-1 text-xs text-red-700 hover:bg-red-50 disabled:opacity-40 dark:border-red-900 dark:text-red-300 dark:hover:bg-red-950">Deactivate</button>}
            </div></td>
          </tr>)}</tbody>
        </table>
        {!rows.length && <EmptyRows message="No users match your search and filters." clear={() => { setQuery(""); setFilter("all"); }} />}
      </Card>
    </Page>
  );
}

export function SecurityPage() {
  const { data, error, loading, reload } = useApi<SecurityResponse>("/security");
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const [sort, setSort] = useState("severity");
  const [direction, setDirection] = useState<"asc" | "desc">("asc");
  const [working, setWorking] = useState("");
  const [actionError, setActionError] = useState("");
  const severityRank: Record<Finding["severity"], number> = { High: 3, Medium: 2, Low: 1 };
  const rows = useMemo(() => {
    const filtered = (data?.items ?? []).filter((item) =>
      `${item.title} ${item.application} ${item.affected} ${item.recommendation}`.toLowerCase().includes(query.toLowerCase())
      && (filter === "all" || (filter === "open" ? item.status === "Open" : filter === "resolved" ? item.status === "Resolved" : item.severity === filter)),
    );
    return sortValue(filtered, (item) => sort === "application" ? item.application : sort === "status" ? item.status : severityRank[item.severity], direction);
  }, [data, query, filter, sort, direction]);
  const onSort = (key: string) => changeSort(key, sort, direction, setSort, setDirection);

  async function resolve(finding: Finding) {
    setWorking(finding.id);
    setActionError("");
    try {
      await requestApi<SecurityResponse>(`/security/${finding.id}/resolve`, { method: "POST" });
      reload();
    } catch (cause) {
      setActionError(cause instanceof Error ? cause.message : "Could not update finding.");
    } finally {
      setWorking("");
    }
  }

  if (!data) return <Page title="Security" sub="Review simulated SaaS security findings and remediation status."><LoadState loading={loading} error={error} retry={reload} /></Page>;
  return (
    <Page title="Security" sub="Review simulated SaaS security findings and remediation status.">
      <div className="mb-4 grid gap-3 sm:grid-cols-2">
        <Metric label="Open findings" value={String(data.summary.open)} />
        <Metric label="High severity" value={String(data.summary.high)} detail="Requires review" />
      </div>
      <PrototypeNote>All findings below are simulated mock examples for this prototype. No security scanning, vendor checks, or live monitoring is implemented.</PrototypeNote>
      <ActionError message={actionError} />
      <div className="mb-3 flex flex-wrap gap-2">
        <input aria-label="Search security findings" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search findings, apps, or users" className={`${controlClass} min-w-48 flex-1 sm:max-w-xs`} />
        <select aria-label="Filter security findings" value={filter} onChange={(event) => setFilter(event.target.value)} className={controlClass}>
          <option value="all">All findings</option><option value="open">Open</option><option value="resolved">Resolved</option><option value="High">High severity</option><option value="Medium">Medium severity</option><option value="Low">Low severity</option>
        </select>
      </div>
      <Card className="overflow-x-auto p-0">
        <table className="w-full min-w-[940px] text-sm">
          <thead className="bg-stone-50 dark:bg-stone-800/50"><tr>
            {tableHeader("Finding", "title", sort, direction, onSort)}
            {tableHeader("Affected application", "application", sort, direction, onSort)}
            {tableHeader("Severity", "severity", sort, direction, onSort)}
            <th className="px-4 py-2.5 text-left text-xs font-medium text-stone-500">Affected users / scope</th>
            <th className="px-4 py-2.5 text-left text-xs font-medium text-stone-500">Recommended remediation</th>
            {tableHeader("Status", "status", sort, direction, onSort)}
            <th className="px-4 py-2.5 text-left text-xs font-medium text-stone-500">Action</th>
          </tr></thead>
          <tbody>{rows.map((finding) => <tr key={finding.id} className="border-t border-stone-100 align-top dark:border-stone-800">
            <td className="max-w-xs px-4 py-3 font-medium">{finding.title}</td><td className="px-4 py-3">{finding.application}</td>
            <td className="px-4 py-3"><Badge tone={finding.severity === "High" ? "red" : finding.severity === "Medium" ? "yellow" : "green"}>{finding.severity}</Badge></td>
            <td className="px-4 py-3">{finding.affected}</td><td className="max-w-md px-4 py-3 text-stone-600 dark:text-stone-300">{finding.recommendation}</td>
            <td className="px-4 py-3">{finding.status === "Open" ? <Badge tone="yellow">Open</Badge> : <Badge tone="green">Resolved</Badge>}</td>
            <td className="px-4 py-3"><button disabled={finding.status === "Resolved" || working === finding.id} onClick={() => resolve(finding)} className="whitespace-nowrap rounded-lg border border-stone-200 px-2.5 py-1.5 text-xs hover:bg-stone-50 disabled:opacity-40 dark:border-stone-700 dark:hover:bg-stone-800">{working === finding.id ? "Saving…" : finding.status === "Resolved" ? "Resolved" : "Mark resolved"}</button></td>
          </tr>)}</tbody>
        </table>
        {!rows.length && <EmptyRows message="No findings match your search and filters." clear={() => { setQuery(""); setFilter("all"); }} />}
      </Card>
    </Page>
  );
}
