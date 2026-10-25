
import React from "react";
import { createRoot } from "react-dom/client";
import {
  BrowserRouter,
  NavLink,
  Route,
  Routes,
  Navigate,
} from "react-router-dom";
import {
  BarChart3,
  Boxes,
  Moon,
  PiggyBank,
  KeyRound,
  CalendarClock,
  Search,
  ShieldCheck,
  LockKeyhole,
  FileText,
} from "lucide-react";
import "./index.css";

import Overview from "./pages/Overview";
import Applications, { AppDetail } from "./pages/Applications";
import Savings from "./pages/Savings";
import FeaturePage from "./pages/FeaturePage";
import {
  AccessPage,
  LicensesPage,
  RenewalsPage,
  SecurityPage,
  ShadowItPage,
} from "./pages/ManagedPages";

const nav = [
  { to: "/", label: "Overview", Icon: BarChart3 },
  { to: "/apps", label: "Applications", Icon: Boxes },
  { to: "/savings", label: "Savings", Icon: PiggyBank },
  { to: "/licenses", label: "Licenses", Icon: KeyRound },
  { to: "/renewals", label: "Renewals", Icon: CalendarClock },
  { to: "/shadow-it", label: "Shadow IT", Icon: Search },
  { to: "/access", label: "Access", Icon: LockKeyhole },
  { to: "/security", label: "Security", Icon: ShieldCheck },
  { to: "/reports", label: "Reports", Icon: FileText },
];

function Shell() {
  return (
    <div className="flex min-h-screen bg-stone-50 text-stone-900 dark:bg-stone-950 dark:text-stone-100">
      <aside className="sticky top-0 hidden h-screen w-56 shrink-0 flex-col gap-1 border-r border-stone-200 bg-white p-3 md:flex dark:border-stone-800 dark:bg-stone-900">
        <div className="px-2 pb-5 pt-1 text-lg font-semibold">
          SaaSSpend
        </div>

        {nav.map(({ to, label, Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) =>
              `flex items-center gap-2 rounded-lg px-2.5 py-2 text-sm font-medium transition ${
                isActive
                  ? "bg-stone-100 text-stone-900 dark:bg-stone-800 dark:text-white"
                  : "text-stone-500 hover:bg-stone-100 dark:text-stone-400 dark:hover:bg-stone-800"
              }`
            }
          >
            <Icon size={16} />
            {label}
          </NavLink>
        ))}
      </aside>

      <main className="min-w-0 flex-1">
        <header className="flex items-center justify-end gap-3 border-b border-stone-200 px-6 py-3 dark:border-stone-800">
          <button
            aria-label="Toggle dark mode"
            className="rounded-lg border border-stone-200 p-2 hover:bg-stone-100 dark:border-stone-800 dark:hover:bg-stone-800"
            onClick={() =>
              document.documentElement.classList.toggle("dark")
            }
          >
            <Moon size={16} />
          </button>
          <span className="text-sm text-stone-500">NovaLabs · Vivek</span>
        </header>

        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/apps" element={<Applications />} />
          <Route path="/apps/:name" element={<AppDetail />} />
          <Route path="/savings" element={<Savings />} />

          <Route path="/licenses" element={<LicensesPage />} />
          <Route path="/renewals" element={<RenewalsPage />} />
          <Route path="/shadow-it" element={<ShadowItPage />} />
          <Route path="/access" element={<AccessPage />} />
          <Route path="/security" element={<SecurityPage />} />
          <Route
            path="/reports"
            element={<FeaturePage title="Reports" />}
          />

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Shell />
    </BrowserRouter>
  </React.StrictMode>
);
