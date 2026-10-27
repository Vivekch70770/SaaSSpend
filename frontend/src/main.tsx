
import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  BrowserRouter,
  NavLink,
  Route,
  Routes,
  Navigate,
} from "react-router-dom";
import {
  ArrowUpRight,
  BarChart3,
  Boxes,
  Moon,
  PiggyBank,
  Sun,
  KeyRound,
  CalendarClock,
  Search,
  ShieldCheck,
  LockKeyhole,
  FileText,
  Sparkles,
  MessageCircle,
} from "lucide-react";
import "./index.css";

import Overview from "./pages/Overview";
import Applications, { AppDetail } from "./pages/Applications";
import Savings from "./pages/Savings";
import {
  AccessPage,
  LicensesPage,
  RenewalsPage,
  SecurityPage,
  ShadowItPage,
} from "./pages/ManagedPages";
import Reports from "./pages/Reports";
import Assistant from "./pages/Assistant";
import SignIn from "./pages/SignIn";
import { AuthProvider, useAuth } from "./auth/AuthProvider";
import {
  getSelectedOrganizationId,
  requestApi,
  storeSelectedOrganizationId,
} from "./lib/api";

type Organization = {
  id: string;
  name: string;
  role: "owner" | "admin" | "editor" | "viewer";
};

const nav = [
  { to: "/", label: "Overview", Icon: BarChart3 },
  { to: "/apps", label: "Applications", Icon: Boxes },
  { to: "/savings", label: "Savings", Icon: PiggyBank },
  { to: "/assistant", label: "Assistant", Icon: MessageCircle },
  { to: "/licenses", label: "Licenses", Icon: KeyRound },
  { to: "/renewals", label: "Renewals", Icon: CalendarClock },
  { to: "/shadow-it", label: "Shadow IT", Icon: Search },
  { to: "/access", label: "Access", Icon: LockKeyhole },
  { to: "/security", label: "Security", Icon: ShieldCheck },
  { to: "/reports", label: "Reports", Icon: FileText },
];

function Shell() {
  const { signOut, session } = useAuth();
  const [dark, setDark] = useState(() => document.documentElement.classList.contains("dark"));
  const [signOutError, setSignOutError] = useState<string | null>(null);
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [selectedOrganizationId, setSelectedOrganizationId] = useState<string | null>(null);
  const [organizationsLoading, setOrganizationsLoading] = useState(true);
  const [organizationError, setOrganizationError] = useState<string | null>(null);
  const [createOrganizationError, setCreateOrganizationError] = useState<string | null>(null);
  const [organizationLoadAttempt, setOrganizationLoadAttempt] = useState(0);
  const [newOrganizationName, setNewOrganizationName] = useState("");

  useEffect(() => {
    let active = true;
    setOrganizationsLoading(true);
    setOrganizationError(null);
    void requestApi<Organization[]>("/organizations")
      .then((items) => {
        if (!active) return;
        setOrganizations(items);
        const savedId = getSelectedOrganizationId();
        const selected = items.find((item) => item.id === savedId)?.id
          ?? (items.length === 1 ? items[0].id : null);
        storeSelectedOrganizationId(selected);
        setSelectedOrganizationId(selected);
      })
      .catch((cause: unknown) => {
        if (active) {
          setOrganizationError(
            cause instanceof Error ? cause.message : "Could not load organizations.",
          );
        }
      })
      .finally(() => {
        if (active) setOrganizationsLoading(false);
      });
    return () => {
      active = false;
    };
  }, [organizationLoadAttempt, session?.user.id]);

  const selectOrganization = (organizationId: string) => {
    const selected = organizationId || null;
    storeSelectedOrganizationId(selected);
    setSelectedOrganizationId(selected);
  };

  const createOrganization = async () => {
    const name = newOrganizationName.trim();
    if (!name) return;
    setCreateOrganizationError(null);
    try {
      const created = await requestApi<Organization>("/organizations", {
        method: "POST",
        body: JSON.stringify({ name }),
      });
      setOrganizations((current) => [...current, created]);
      setNewOrganizationName("");
      selectOrganization(created.id);
    } catch (cause) {
      setCreateOrganizationError(
        cause instanceof Error ? cause.message : "Could not create organization.",
      );
    }
  };

  const selectedOrganization = organizations.find(
    (organization) => organization.id === selectedOrganizationId,
  );
  const toggleTheme = () => {
    const nextDark = !document.documentElement.classList.contains("dark");
    document.documentElement.classList.toggle("dark", nextDark);
    setDark(nextDark);
  };
  const handleSignOut = async () => {
    setSignOutError(null);
    try {
      await signOut();
    } catch (error) {
      setSignOutError(error instanceof Error ? error.message : "Sign-out failed.");
    }
  };
  const initials = session?.user.email?.slice(0, 2).toUpperCase() ?? "SP";

  return (
    <div className="app-shell flex min-h-screen bg-stone-50 text-stone-900 dark:bg-[#0b0c09] dark:text-stone-100">
      <aside className="sidebar sticky top-0 hidden h-screen w-[244px] shrink-0 flex-col border-r border-stone-200 bg-white px-4 pb-4 pt-5 dark:border-white/[.06] dark:bg-[#0e0f0c] md:flex">
        <NavLink to="/" className="mb-9 flex items-center gap-3 px-2">
          <span className="grid size-9 place-items-center rounded-xl bg-[#c6f36a] text-[#16190f] shadow-[0_5px_18px_rgba(198,243,106,.16)]">
            <Sparkles size={18} strokeWidth={2.3} />
          </span>
          <span>
            <span className="block text-[15px] font-semibold tracking-[-.03em] text-stone-900 dark:text-white">saas<span className="text-[#a6d84d]">spend</span></span>
            <span className="mt-0.5 block text-[9px] font-semibold uppercase tracking-[.19em] text-stone-500">Spend intelligence</span>
          </span>
        </NavLink>

        <p className="mb-2 px-3 text-[9px] font-semibold uppercase tracking-[.18em] text-stone-500">Workspace</p>
        <div className="space-y-1">
          {nav.slice(0, 4).map(({ to, label, Icon }) => (
            <NavLink key={to} to={to} end={to === "/"} className={({ isActive }) => `sidebar-link ${isActive ? "sidebar-link-active" : ""}`}>
              <Icon size={16} strokeWidth={1.8} />
              <span>{label}</span>
              {label === "Overview" && <span className="ml-auto size-1.5 rounded-full bg-[#c6f36a]" />}
            </NavLink>
          ))}
        </div>

        <p className="mb-2 mt-8 px-3 text-[9px] font-semibold uppercase tracking-[.18em] text-stone-500">Manage</p>
        <div className="space-y-1">
          {nav.slice(4).map(({ to, label, Icon }) => (
            <NavLink key={to} to={to} className={({ isActive }) => `sidebar-link ${isActive ? "sidebar-link-active" : ""}`}>
              <Icon size={16} strokeWidth={1.8} />
              <span>{label}</span>
            </NavLink>
          ))}
        </div>

        <div className="mt-auto rounded-2xl border border-[#c6f36a]/10 bg-[#c6f36a]/[.035] p-3.5">
          <div className="flex items-center gap-2 text-[10px] font-medium text-stone-300">
            <Sparkles size={13} className="text-[#c6f36a]" />
            Spend insights
          </div>
          <p className="mt-2 text-[10px] leading-4 text-stone-500">Review trends across your software stack.</p>
          <NavLink to="/reports" className="mt-3 inline-flex items-center gap-1 text-[10px] font-medium text-[#c6f36a] hover:text-[#e0ffa0]">
            Explore reports <ArrowUpRight size={12} />
          </NavLink>
        </div>

        <div className="mt-4 flex items-center gap-2.5 border-t border-white/[.06] px-1 pt-4">
          <span className="grid size-8 place-items-center rounded-full bg-gradient-to-br from-[#d9f5a1] to-[#768d4c] text-[10px] font-semibold text-[#171a12]">{initials}</span>
          <span className="min-w-0 flex-1">
            <span className="block truncate text-xs font-medium text-stone-200">{session?.user.email}</span>
            <span className="mt-0.5 block truncate text-[10px] text-stone-500">SaaSSpend workspace</span>
          </span>
        </div>
      </aside>

      <main className="min-w-0 flex-1">
        <header className="topbar flex h-[62px] items-center justify-between border-b border-stone-200 px-4 dark:border-white/[.06] sm:px-6 lg:px-9">
          <div className="flex items-center gap-2 text-xs text-stone-500">
            <span className="font-medium text-stone-700 dark:text-stone-300">Workspace</span>
            <span className="text-stone-600">/</span>
            <span>{selectedOrganization?.name ?? "Select organization"}</span>
          </div>
          <div className="flex items-center gap-2.5">
            {organizations.length > 0 && (
              <select
                aria-label="Select organization"
                value={selectedOrganizationId ?? ""}
                onChange={(event) => selectOrganization(event.target.value)}
                className="max-w-40 rounded-lg border border-stone-200 bg-white px-2 py-1.5 text-[11px] text-stone-700 dark:border-white/[.08] dark:bg-[#0e0f0c] dark:text-stone-300"
              >
                <option value="" disabled>Select organization</option>
                {organizations.map((organization) => (
                  <option key={organization.id} value={organization.id}>
                    {organization.name}
                  </option>
                ))}
              </select>
            )}
            <span className="hidden text-[11px] text-stone-500 sm:inline">{session?.user.email}</span>
            <button
              type="button"
              onClick={() => void handleSignOut()}
              className="rounded-lg border border-stone-200 px-2.5 py-1.5 text-[11px] text-stone-500 transition hover:bg-stone-100 dark:border-white/[.08] dark:text-stone-400 dark:hover:bg-white/[.06]"
            >
              Sign out
            </button>
            <button
              type="button"
              aria-label={`Switch to ${dark ? "light" : "dark"} mode`}
              aria-pressed={dark}
              className="theme-toggle grid size-8 place-items-center rounded-lg border border-stone-200 text-stone-500 transition hover:bg-stone-100 dark:border-white/[.08] dark:text-stone-400 dark:hover:bg-white/[.06]"
              onClick={toggleTheme}
            >
              {dark ? <Sun size={15} /> : <Moon size={15} />}
            </button>
            <span className="grid size-8 place-items-center rounded-full border border-white/[.08] bg-[#c6f36a]/10 text-[10px] font-semibold text-[#c6f36a] sm:hidden">{initials}</span>
          </div>
        </header>
        {signOutError && (
          <p role="alert" className="px-4 pt-3 text-sm text-red-600 dark:text-red-300">
            {signOutError}
          </p>
        )}

        <nav aria-label="Mobile navigation" className="mobile-nav flex gap-1 overflow-x-auto border-b border-stone-200 px-3 py-2 dark:border-white/[.06] md:hidden">
          {nav.map(({ to, label, Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) => `mobile-nav-link ${isActive ? "mobile-nav-link-active" : ""}`}
            >
              <Icon size={14} />
              {label}
            </NavLink>
          ))}
        </nav>

        {organizationsLoading ? (
          <p className="p-6 text-sm text-stone-500">Loading organizations...</p>
        ) : organizationError ? (
          <div className="p-6">
            <p role="alert" className="text-sm text-red-600 dark:text-red-300">
              {organizationError}
            </p>
            <button
              type="button"
              onClick={() => setOrganizationLoadAttempt((attempt) => attempt + 1)}
              className="mt-2 text-sm underline"
            >
              Retry
            </button>
          </div>
        ) : organizations.length === 0 ? (
          <section className="mx-auto mt-10 max-w-md rounded-2xl border border-stone-200 bg-white p-5 dark:border-white/[.08] dark:bg-[#0e0f0c]">
            <h1 className="text-base font-semibold">Create an organization</h1>
            <p className="mt-1 text-sm text-stone-500">Your account is not a member of an organization yet.</p>
            <div className="mt-4 flex gap-2">
              <input
                aria-label="Organization name"
                value={newOrganizationName}
                maxLength={100}
                onChange={(event) => setNewOrganizationName(event.target.value)}
                className="min-w-0 flex-1 rounded-lg border border-stone-200 bg-white px-3 py-2 text-sm dark:border-white/[.08] dark:bg-[#0b0c09]"
              />
              <button
                type="button"
                onClick={() => void createOrganization()}
                className="rounded-lg bg-stone-900 px-3 py-2 text-sm font-medium text-white dark:bg-white dark:text-stone-900"
              >
                Create
              </button>
            </div>
            {createOrganizationError && (
              <p role="alert" className="mt-3 text-sm text-red-600 dark:text-red-300">
                {createOrganizationError}
              </p>
            )}
          </section>
        ) : !selectedOrganization ? (
          <p className="p-6 text-sm text-stone-500">Select an organization to continue.</p>
        ) : (
          <Routes key={selectedOrganizationId}>
            <Route path="/" element={<Overview />} />
            <Route path="/apps" element={<Applications />} />
            <Route path="/apps/:name" element={<AppDetail />} />
            <Route path="/savings" element={<Savings />} />
            <Route path="/assistant" element={<Assistant />} />

            <Route path="/licenses" element={<LicensesPage />} />
            <Route path="/renewals" element={<RenewalsPage />} />
            <Route path="/shadow-it" element={<ShadowItPage />} />
            <Route path="/access" element={<AccessPage />} />
            <Route path="/security" element={<SecurityPage />} />
            <Route path="/reports" element={<Reports />} />

            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        )}
      </main>
    </div>
  );
}

function AppRoot() {
  const { accessChecking, accessError, loading, session } = useAuth();

  if (loading || (session && accessChecking)) {
    return <main className="grid min-h-screen place-items-center text-sm text-stone-500">Loading your session...</main>;
  }
  if (!session || accessError) return <SignIn />;
  return <Shell key={session?.user.id} />;
}

document.documentElement.classList.add("dark");

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AuthProvider>
      <BrowserRouter>
        <AppRoot />
      </BrowserRouter>
    </AuthProvider>
  </React.StrictMode>
);
