import { useState, type FormEvent } from "react";
import { Sparkles } from "lucide-react";
import { useAuth } from "../auth/AuthProvider";

export default function SignIn() {
  const {
    accessError,
    configured,
    retryAccessCheck,
    session,
    sessionError,
    signInWithGoogle,
    signInWithPassword,
    signOut,
  } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setPending(true);
    try {
      await signInWithPassword(email, password);
    } catch (signInError) {
      setError(signInError instanceof Error ? signInError.message : "Sign-in failed.");
    } finally {
      setPending(false);
    }
  }

  async function signInGoogle() {
    setError(null);
    setPending(true);
    try {
      await signInWithGoogle();
    } catch (signInError) {
      setError(signInError instanceof Error ? signInError.message : "Google sign-in failed.");
      setPending(false);
    }
  }

  async function leaveUnauthorizedSession() {
    try {
      await signOut();
    } catch (signOutError) {
      setError(signOutError instanceof Error ? signOutError.message : "Sign-out failed.");
    }
  }

  return (
    <main className="grid min-h-screen place-items-center bg-stone-50 px-4 py-10 dark:bg-[#0b0c09]">
      <section className="w-full max-w-md rounded-2xl border border-stone-200 bg-white p-7 shadow-xl dark:border-white/[.08] dark:bg-[#111310] sm:p-9">
        <div className="mb-7 flex items-center gap-3">
          <span className="grid size-10 place-items-center rounded-xl bg-[#c6f36a] text-[#16190f]">
            <Sparkles size={19} strokeWidth={2.3} />
          </span>
          <span className="text-lg font-semibold tracking-[-.03em] text-stone-900 dark:text-white">
            SaaS<span className="text-[#8dbd39]">Spend</span>
          </span>
        </div>
        <h1 className="text-xl font-semibold tracking-tight text-stone-900 dark:text-white">
          Sign in to your workspace
        </h1>
        <p className="mt-2 text-sm leading-6 text-stone-500">
          Continue with your authorized SaaSSpend account.
        </p>

        {!configured ? (
          <p role="alert" className="mt-6 rounded-xl border border-amber-500/20 bg-amber-500/10 p-3 text-sm text-amber-700 dark:text-amber-200">
            Supabase Auth is not configured. Set the frontend environment variables and restart the app.
          </p>
        ) : session && accessError ? (
          <div role="alert" className="mt-6 rounded-xl border border-amber-500/20 bg-amber-500/10 p-3 text-sm leading-6 text-amber-700 dark:text-amber-200">
            {accessError === "forbidden"
              ? "This account cannot access SaaSSpend yet. Contact your administrator."
              : accessError === "unauthorized"
                ? "Your sign-in session was rejected. Sign out and sign in again."
                : "Unable to verify access right now. Check your connection and retry."}
            {error && <p className="mt-2 text-red-700 dark:text-red-200">{error}</p>}
            {accessError === "transient" && (
              <button
                type="button"
                className="mt-3 block font-medium underline"
                onClick={retryAccessCheck}
              >
                Retry access check
              </button>
            )}
            <button
              type="button"
              className="mt-3 block font-medium underline"
              onClick={() => void leaveUnauthorizedSession()}
            >
              Sign out
            </button>
          </div>
        ) : (
          <>
            {error && (
              <p role="alert" className="mt-5 rounded-xl border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-700 dark:text-red-200">
                {error}
              </p>
            )}
            {sessionError && (
              <p role="alert" className="mt-5 rounded-xl border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-700 dark:text-red-200">
                {sessionError}
              </p>
            )}
            <button
              type="button"
              disabled={pending}
              onClick={() => void signInGoogle()}
              className="mt-6 w-full rounded-xl border border-stone-200 px-4 py-3 text-sm font-medium text-stone-800 transition hover:bg-stone-50 disabled:opacity-60 dark:border-white/[.12] dark:text-stone-100 dark:hover:bg-white/[.04]"
            >
              Continue with Google
            </button>
            <div className="my-5 flex items-center gap-3 text-xs text-stone-400">
              <span className="h-px flex-1 bg-stone-200 dark:bg-white/[.08]" />
              or continue with email
              <span className="h-px flex-1 bg-stone-200 dark:bg-white/[.08]" />
            </div>
            <form className="space-y-4" onSubmit={(event) => void submit(event)}>
              <label className="block text-sm font-medium text-stone-700 dark:text-stone-300">
                Email
                <input
                  required
                  autoComplete="email"
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  className="mt-1.5 w-full rounded-xl border border-stone-200 bg-transparent px-3 py-2.5 text-sm outline-none focus:border-[#8dbd39] dark:border-white/[.12]"
                />
              </label>
              <label className="block text-sm font-medium text-stone-700 dark:text-stone-300">
                Password
                <input
                  required
                  autoComplete="current-password"
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  className="mt-1.5 w-full rounded-xl border border-stone-200 bg-transparent px-3 py-2.5 text-sm outline-none focus:border-[#8dbd39] dark:border-white/[.12]"
                />
              </label>
              <button
                type="submit"
                disabled={pending}
                className="w-full rounded-xl bg-[#c6f36a] px-4 py-3 text-sm font-semibold text-[#171a12] transition hover:bg-[#d5fa8a] disabled:opacity-60"
              >
                {pending ? "Signing in..." : "Sign in"}
              </button>
            </form>
          </>
        )}
      </section>
    </main>
  );
}
