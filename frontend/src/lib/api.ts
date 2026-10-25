
import { useEffect, useState } from "react";

const API_BASE = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000";

export async function requestApi<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}/api${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    let message = `API error: ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) message = body.detail;
    } catch {
      // Keep the HTTP status message when the server response is not JSON.
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

export type App = {
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

export type Opp = {
  type: string;
  app: string;
  monthly: number;
  annual: number;
  confidence: string;
  why: string;
  utilization: number;
  active: number;
  licenses: number;
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
