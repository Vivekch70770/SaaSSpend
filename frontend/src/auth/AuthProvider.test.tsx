import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import type { Session } from "@supabase/supabase-js";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider, useAuth } from "./AuthProvider";

const authMocks = vi.hoisted(() => ({
  getSession: vi.fn(),
  onAuthStateChange: vi.fn(),
  signInWithOAuth: vi.fn(),
  signInWithPassword: vi.fn(),
  signOut: vi.fn(),
}));

vi.mock("../lib/supabase", () => ({
  supabase: {
    auth: {
      getSession: authMocks.getSession,
      onAuthStateChange: authMocks.onAuthStateChange,
      signInWithOAuth: authMocks.signInWithOAuth,
      signInWithPassword: authMocks.signInWithPassword,
      signOut: authMocks.signOut,
    },
  },
}));

let currentSession: Session | null;
let notifyAuthState: ((event: string, session: Session | null) => void) | undefined;
let fetchMock: ReturnType<typeof vi.fn>;

function makeSession(token: string, userId = "test-user"): Session {
  return {
    access_token: token,
    token_type: "bearer",
    expires_in: 3600,
    expires_at: 2_000_000_000,
    refresh_token: "synthetic-refresh-token",
    user: { id: userId },
  } as Session;
}

function makeResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

function Probe() {
  const {
    accessChecking,
    accessError,
    loading,
    retryAccessCheck,
    session,
    sessionError,
    signOut,
  } = useAuth();

  return (
    <div>
      <output data-testid="loading">{String(loading)}</output>
      <output data-testid="session">{session?.user.id ?? "none"}</output>
      <output data-testid="session-error">{sessionError ?? "none"}</output>
      <output data-testid="access-checking">{String(accessChecking)}</output>
      <output data-testid="access-error">{accessError ?? "none"}</output>
      <button onClick={retryAccessCheck}>Retry</button>
      <button onClick={() => void signOut()}>Sign out</button>
    </div>
  );
}

function renderProvider() {
  return render(
    <AuthProvider>
      <Probe />
    </AuthProvider>,
  );
}

function emitAuthState(event: string, session: Session | null) {
  currentSession = session;
  act(() => notifyAuthState?.(event, session));
}

describe("AuthProvider", () => {
  beforeEach(() => {
    currentSession = null;
    notifyAuthState = undefined;
    authMocks.getSession.mockReset().mockImplementation(async () => ({
      data: { session: currentSession },
      error: null,
    }));
    authMocks.onAuthStateChange.mockReset().mockImplementation((callback) => {
      notifyAuthState = callback;
      return {
        data: { subscription: { unsubscribe: vi.fn() } },
      };
    });
    authMocks.signOut.mockReset().mockImplementation(async () => {
      emitAuthState("SIGNED_OUT", null);
      return { error: null };
    });
    fetchMock = vi.fn().mockResolvedValue(
      makeResponse(200, { authenticated: true }),
    );
    vi.stubGlobal("fetch", fetchMock);
    vi.spyOn(console, "warn").mockImplementation(() => undefined);
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("keeps initial loading active while restoring the session", async () => {
    let finishRestore!: (value: {
      data: { session: Session | null };
      error: null;
    }) => void;
    authMocks.getSession.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finishRestore = resolve;
        }),
    );

    renderProvider();
    expect(screen.getByTestId("loading").textContent).toBe("true");

    await act(async () => {
      finishRestore({ data: { session: null }, error: null });
    });

    expect(screen.getByTestId("loading").textContent).toBe("false");
    expect(screen.getByTestId("session").textContent).toBe("none");
  });

  it("does not overwrite a newer auth event with stale restored session data", async () => {
    let finishRestore!: (value: {
      data: { session: Session | null };
      error: null;
    }) => void;
    authMocks.getSession.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finishRestore = resolve;
        }),
    );

    renderProvider();
    const newerSession = makeSession("new-session-token", "new-user");
    emitAuthState("SIGNED_IN", newerSession);
    await waitFor(() =>
      expect(screen.getByTestId("session").textContent).toBe("new-user"),
    );

    await act(async () => {
      finishRestore({
        data: { session: makeSession("stale-token", "stale-user") },
        error: null,
      });
    });

    expect(screen.getByTestId("session").textContent).toBe("new-user");
    await waitFor(() => expect(screen.getByTestId("access-checking").textContent).toBe("false"));
  });

  it("clears the authenticated session after sign-out", async () => {
    currentSession = makeSession("current-session-token");
    renderProvider();
    await waitFor(() =>
      expect(screen.getByTestId("access-checking").textContent).toBe("false"),
    );

    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));

    await waitFor(() => {
      expect(screen.getByTestId("session").textContent).toBe("none");
      expect(screen.getByTestId("access-error").textContent).toBe("none");
    });
  });

  it.each([
    [401, "unauthorized"],
    [403, "forbidden"],
  ] as const)("classifies HTTP %i as %s", async (status, expectedError) => {
    currentSession = makeSession("current-session-token");
    fetchMock.mockResolvedValueOnce(makeResponse(status, { detail: "rejected" }));

    renderProvider();

    await waitFor(() =>
      expect(screen.getByTestId("access-error").textContent).toBe(expectedError),
    );
  });

  it("offers retry after a transient network failure", async () => {
    currentSession = makeSession("current-session-token");
    fetchMock
      .mockRejectedValueOnce(new TypeError("network unavailable"))
      .mockResolvedValueOnce(makeResponse(200, { authenticated: true }));

    renderProvider();

    await waitFor(() =>
      expect(screen.getByTestId("access-error").textContent).toBe("transient"),
    );
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));

    await waitFor(() =>
      expect(screen.getByTestId("access-error").textContent).toBe("none"),
    );
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("uses the current access token again after a token refresh event", async () => {
    currentSession = makeSession("initial-access-token");
    renderProvider();

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    emitAuthState("TOKEN_REFRESHED", makeSession("refreshed-access-token"));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    const request = fetchMock.mock.calls[1][1] as RequestInit;
    expect(new Headers(request.headers).get("Authorization")).toBe(
      "Bearer refreshed-access-token",
    );
  });
});
