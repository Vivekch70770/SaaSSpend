import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { getSession } = vi.hoisted(() => ({ getSession: vi.fn() }));

vi.mock("./supabase", () => ({
  supabase: { auth: { getSession } },
}));

import {
  requestApi,
  storeSelectedOrganizationId,
} from "./api";

describe("requestApi organization context", () => {
  beforeEach(() => {
    vi.resetModules();
    localStorage.clear();
    getSession.mockReset();
    getSession.mockResolvedValue({
      data: { session: { access_token: "test-access-token" } },
      error: null,
    });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => [],
      }),
    );
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  it("sends the selected organization with business API requests", async () => {
    storeSelectedOrganizationId("org-a");

    await requestApi("/apps");

    const [, init] = vi.mocked(fetch).mock.calls[0];
    expect(new Headers(init?.headers).get("X-Organization-ID")).toBe("org-a");
  });

  it("does not require or send organization context when listing memberships", async () => {
    storeSelectedOrganizationId("org-a");

    await requestApi("/organizations");

    const [, init] = vi.mocked(fetch).mock.calls[0];
    expect(new Headers(init?.headers).has("X-Organization-ID")).toBe(false);
  });

  it.each([
    "",
    "not-an-absolute-url",
    "http://api.example.test",
  ])(
    "rejects production API configuration before fetching or reading a bearer token: %s",
    async (configuredUrl) => {
      vi.stubEnv("PROD", true);
      vi.stubEnv("VITE_API_URL", configuredUrl);
      localStorage.clear();

      await expect(import("./api")).rejects.toThrow();

      expect(fetch).not.toHaveBeenCalled();
      expect(getSession).not.toHaveBeenCalled();
      expect(vi.mocked(fetch).mock.calls).toHaveLength(0);
    },
  );
});
