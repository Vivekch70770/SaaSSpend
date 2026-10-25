import { ReactNode } from "react";
export const Card = ({ children, className = "", onClick }: { children: ReactNode; className?: string; onClick?: () => void }) => (
  <div onClick={onClick} className={`rounded-2xl border border-stone-200 bg-white p-5 shadow-sm transition dark:border-stone-800 dark:bg-stone-900 ${onClick ? "cursor-pointer hover:-translate-y-px hover:shadow-lg" : ""} ${className}`}>{children}</div>
);
const tones = { green: "bg-green-50 text-green-700 dark:bg-green-950 dark:text-green-400", yellow: "bg-yellow-50 text-yellow-700 dark:bg-yellow-950 dark:text-yellow-400", red: "bg-red-50 text-red-700 dark:bg-red-950 dark:text-red-400" };
export const Badge = ({ tone, children }: { tone: keyof typeof tones; children: ReactNode }) => <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${tones[tone]}`}>{children}</span>;
export const riskTone = { Low: "green", Medium: "yellow", High: "red" } as const;
export const Page = ({ title, sub, children }: { title: string; sub: string; children: ReactNode }) => (
  <div className="mx-auto max-w-6xl p-8"><h1 className="text-2xl font-semibold tracking-tight">{title}</h1><p className="mb-6 text-stone-500">{sub}</p>{children}</div>
);
export const Loading = ({ error }: { error: boolean }) => (
  <div className="p-8 text-stone-500">{error ? "Can't reach the API. Start the backend with: uvicorn main:app --reload" : "Loading…"}</div>
);
