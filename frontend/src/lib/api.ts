
import { useEffect, useState } from "react";
import { supabase } from "./supabase";
import { resolveApiBase } from "./apiBase";

const API_BASE = resolveApiBase(
  import.meta.env.VITE_API_URL ??
    (import.meta.env.PROD ? undefined : "http://127.0.0.1:8000"),
  import.meta.env.PROD,
);
const ORGANIZATION_STORAGE_KEY = "saasspend.selectedOrganizationId";

export function getSelectedOrganizationId(): string | null {
  return window.localStorage.getItem(ORGANIZATION_STORAGE_KEY);
}

export function storeSelectedOrganizationId(organizationId: string | null): void {
  if (organizationId) {
    window.localStorage.setItem(ORGANIZATION_STORAGE_KEY, organizationId);
  } else {
    window.localStorage.removeItem(ORGANIZATION_STORAGE_KEY);
  }
}

export class ApiRequestError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly authorizationPresent: boolean,
  ) {
    super(message);
    this.name = "ApiRequestError";
  }
}

export async function requestApi<T>(path: string, init?: RequestInit): Promise<T> {
  const { data, error } = supabase
    ? await supabase.auth.getSession()
    : { data: { session: null }, error: new Error("Supabase Auth is not configured.") };
  if (error) throw error;

  const headers = new Headers(init?.headers);
  if (!headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const accessToken = data.session?.access_token;
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);

  if (path !== "/organizations" && path !== "/auth/me") {
    const organizationId = getSelectedOrganizationId();
    if (organizationId) headers.set("X-Organization-ID", organizationId);
  }

  const response = await fetch(`${API_BASE}/api${path}`, {
    ...init,
    headers,
  });
  if (!response.ok) {
    let message = `API error: ${response.status}`;
    try {
      const body = (await response.json()) as {
        detail?: string | { msg?: string }[];
      };
      if (typeof body.detail === "string") {
        message = body.detail;
      } else if (body.detail?.length) {
        message = body.detail.map((issue) => issue.msg ?? "Invalid value").join("; ");
      }
    } catch {
      // Keep the HTTP status message when the server response is not JSON.
    }
    throw new ApiRequestError(
      message,
      response.status,
      headers.has("Authorization"),
    );
  }
  if (response.status === 204 || response.status === 205) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export type App = {
  id: string;
  name: string;
  category: string;
  cost: number;
  licenses: number;
  active: number;
  idle: number;
  annual: number;
  risk: "Low" | "Medium" | "High";
  renewal: string;
  utilization: number;
  savings: number;
};

export type AppInput = Pick<App, "name" | "category" | "cost" | "licenses" | "active" | "risk" | "renewal">;

export type Opp = {
  type: string;
  app: string;
  monthly: number;
  estimated_monthly_savings: number;
  annual: number;
  confidence: string;
  why: string;
  utilization: number;
  active: number;
  licenses: number;
  unused: number;
  seat_cost: number;
};

export function useApi<T>(path: string) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    let cancelled = false;

    setData(null);
    setError(false);
    setLoading(true);

    requestApi<T>(path)
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch(() => {
        if (!cancelled) setError(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [path, revision]);

  return { data, error, loading, reload: () => setRevision((value) => value + 1) };
}
