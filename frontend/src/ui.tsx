import { ReactNode } from "react";
import { LoaderCircle } from "lucide-react";

export const Card = ({
  children,
  className = "",
  onClick,
}: {
  children: ReactNode;
  className?: string;
  onClick?: () => void;
}) => (
  <div
    onClick={onClick}
    className={`rounded-[20px] border border-stone-200 bg-white p-5 shadow-sm transition dark:border-white/[.075] dark:bg-[#111310] dark:shadow-[0_8px_32px_rgba(0,0,0,.12)] ${
      onClick ? "cursor-pointer hover:-translate-y-px hover:shadow-lg" : ""
    } ${className}`}
  >
    {children}
  </div>
);

const tones = {
  green: "bg-green-50 text-green-700 dark:bg-[#c6f36a]/10 dark:text-[#c6f36a]",
  yellow: "bg-yellow-50 text-yellow-700 dark:bg-amber-300/10 dark:text-amber-200",
  red: "bg-red-50 text-red-700 dark:bg-rose-400/10 dark:text-rose-300",
};
export const Badge = ({ tone, children }: { tone: keyof typeof tones; children: ReactNode }) => (
  <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${tones[tone]}`}>{children}</span>
);
export const riskTone = { Low: "green", Medium: "yellow", High: "red" } as const;

export const Page = ({
  title,
  sub,
  children,
  action,
}: {
  title: string;
  sub: string;
  children: ReactNode;
  action?: ReactNode;
}) => (
  <div className="mx-auto w-full max-w-[1440px] px-4 pb-10 pt-7 sm:px-6 sm:pt-9 lg:px-9 lg:pt-10">
    <div className="mb-7 flex flex-wrap items-end justify-between gap-4 sm:mb-8">
      <div>
        <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-[.2em] text-stone-500">SaaSSpend / Workspace</p>
        <h1 className="text-[26px] font-semibold tracking-[-.04em] text-stone-950 dark:text-stone-50 sm:text-[30px]">{title}</h1>
        <p className="mt-1.5 max-w-2xl text-sm leading-6 text-stone-500 dark:text-stone-400">{sub}</p>
      </div>
      {action}
    </div>
    {children}
  </div>
);

export const Loading = ({
  error,
  loading = true,
  retry,
}: {
  error: boolean;
  loading?: boolean;
  retry?: () => void;
}) => (
  <div
    role={error ? "alert" : "status"}
    className={`flex min-h-40 flex-col items-center justify-center rounded-[20px] border px-5 py-10 text-center ${
      error
        ? "border-rose-400/20 bg-rose-400/[.04] text-rose-200"
        : "border-white/[.06] bg-white/[.02] text-stone-400"
    }`}
  >
    {error ? (
      <>
        <p className="text-sm font-medium">Could not load data from the API.</p>
        <p className="mt-1.5 text-xs text-stone-500">Make sure the FastAPI backend is running, then try again.</p>
        {retry && (
          <button
            type="button"
            onClick={retry}
            className="mt-4 rounded-lg border border-white/10 px-3 py-1.5 text-xs font-medium text-stone-200 transition hover:bg-white/[.06]"
          >
            Retry
          </button>
        )}
      </>
    ) : (
      <>
        <LoaderCircle size={19} className="animate-spin text-[#c6f36a]" />
        <p className="mt-3 text-sm">{loading ? "Loading your workspace…" : "No data available."}</p>
      </>
    )}
  </div>
);
