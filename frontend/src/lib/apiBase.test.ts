import { describe, expect, it } from "vitest";
import { resolveApiBase } from "./apiBase";

describe("resolveApiBase", () => {
  it("requires a configured URL in production", () => {
    expect(() => resolveApiBase(undefined, true)).toThrow(/explicitly configured/);
  });

  it("rejects an empty URL", () => {
    expect(() => resolveApiBase("", true)).toThrow(/explicitly configured/);
  });

  it("rejects malformed URLs", () => {
    expect(() => resolveApiBase("https:// api.example.test", true)).toThrow(/valid absolute URL/);
  });

  it("rejects insecure production URLs", () => {
    expect(() => resolveApiBase("http://api.example.test", true)).toThrow(/must use HTTPS/);
    expect(() => resolveApiBase("http://localhost:8000", true)).toThrow(/must use HTTPS/);
  });

  it("accepts HTTPS production URLs and normalizes trailing slashes", () => {
    expect(resolveApiBase("https://api.example.test/root///", true)).toBe(
      "https://api.example.test/root",
    );
  });

  it.each([
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://[::1]:8000",
  ])("accepts explicit development loopback endpoint %s", (endpoint) => {
    expect(resolveApiBase(endpoint, false)).toBe(endpoint);
  });

  it("rejects non-loopback HTTP endpoints in development", () => {
    expect(() => resolveApiBase("http://api.example.test", false)).toThrow(
      /HTTPS or an explicit HTTP loopback URL/,
    );
  });

  it.each([
    "https://user:pass@api.example.test",
    "https://api.example.test?redirect=elsewhere",
    "https://api.example.test#fragment",
  ])("rejects URL components that can redirect or embed credentials: %s", (endpoint) => {
    expect(() => resolveApiBase(endpoint, true)).toThrow(/unsupported URL components/);
  });
});
