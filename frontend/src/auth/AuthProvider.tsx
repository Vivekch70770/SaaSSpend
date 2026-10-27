import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import type { Session } from "@supabase/supabase-js";
import { ApiRequestError, requestApi } from "../lib/api";
import { supabase } from "../lib/supabase";

type AuthContextValue = {
  session: Session | null;
  loading: boolean;
  sessionError: string | null;
  accessChecking: boolean;
  accessError: "unauthorized" | "forbidden" | "transient" | null;
  configured: boolean;
  retryAccessCheck: () => void;
  signInWithPassword: (email: string, password: string) => Promise<void>;
  signInWithGoogle: () => Promise<void>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [sessionError, setSessionError] = useState<string | null>(null);
  const [accessChecking, setAccessChecking] = useState(false);
  const [accessError, setAccessError] = useState<
    "unauthorized" | "forbidden" | "transient" | null
  >(null);
  const [accessCheckAttempt, setAccessCheckAttempt] = useState(0);
  const authStateChanged = useRef(false);

  useEffect(() => {
    if (!supabase) {
      setLoading(false);
      return;
    }

    let active = true;
    authStateChanged.current = false;
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      if (active) {
        authStateChanged.current = true;
        setSessionError(null);
        setSession(nextSession);
        setAccessChecking(Boolean(nextSession));
        setLoading(false);
      }
    });

    void supabase.auth.getSession().then(({ data, error }) => {
      if (!active) return;
      setLoading(false);
      if (authStateChanged.current) return;
      if (error) {
        setSessionError("Unable to restore your sign-in session.");
        setSession(null);
        return;
      }
      setSessionError(null);
      setSession(data.session);
      setAccessChecking(Boolean(data.session));
    }).catch(() => {
      if (!active) return;
      setLoading(false);
      if (authStateChanged.current) return;
      setSessionError("Unable to restore your sign-in session.");
      setSession(null);
    });

    return () => {
      active = false;
      subscription.unsubscribe();
    };
  }, []);

  useEffect(() => {
    if (!session) {
      setAccessChecking(false);
      setAccessError(null);
      return;
    }

    let active = true;
    setAccessChecking(true);
    setAccessError(null);
    void requestApi<{ authenticated: boolean }>("/auth/me")
      .then(() => {
        if (active) setAccessChecking(false);
      })
      .catch((error: unknown) => {
        console.warn(
          "SaaSSpend access check failed",
          error instanceof ApiRequestError
            ? {
                status: error.status,
                authorizationPresent: error.authorizationPresent,
              }
            : { cause: "request_or_session_error" },
        );
        if (active) {
          setAccessError(
            error instanceof ApiRequestError && error.status === 403
              ? "forbidden"
              : error instanceof ApiRequestError && error.status === 401
                ? "unauthorized"
                : "transient",
          );
          setAccessChecking(false);
        }
      });

    return () => {
      active = false;
    };
  }, [accessCheckAttempt, session]);

  const value = useMemo<AuthContextValue>(
    () => ({
      session,
      loading,
      sessionError,
      accessChecking,
      accessError,
      configured: supabase !== null,
      retryAccessCheck() {
        setAccessCheckAttempt((attempt) => attempt + 1);
      },
      async signInWithPassword(email, password) {
        if (!supabase) throw new Error("Supabase Auth is not configured.");
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) throw error;
      },
      async signInWithGoogle() {
        if (!supabase) throw new Error("Supabase Auth is not configured.");
        const { error } = await supabase.auth.signInWithOAuth({
          provider: "google",
          options: { redirectTo: window.location.origin },
        });
        if (error) throw error;
      },
      async signOut() {
        if (!supabase) throw new Error("Supabase Auth is not configured.");
        const { error } = await supabase.auth.signOut();
        if (error) throw error;
      },
    }),
    [accessChecking, accessError, loading, session, sessionError],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
