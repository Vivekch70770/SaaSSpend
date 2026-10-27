const LOOPBACK_HOSTS = new Set(["localhost", "127.0.0.1", "[::1]"]);

export function resolveApiBase(
  configuredUrl: string | undefined,
  production: boolean,
): string {
  if (!configuredUrl || configuredUrl !== configuredUrl.trim()) {
    throw new Error("VITE_API_URL must be explicitly configured.");
  }

  let url: URL;
  try {
    url = new URL(configuredUrl);
  } catch {
    throw new Error("VITE_API_URL must be a valid absolute URL.");
  }

  if (
    !url.hostname ||
    url.username ||
    url.password ||
    url.search ||
    url.hash
  ) {
    throw new Error("VITE_API_URL contains unsupported URL components.");
  }

  if (production) {
    if (url.protocol !== "https:") {
      throw new Error("Production VITE_API_URL must use HTTPS.");
    }
  } else if (
    url.protocol !== "https:" &&
    !(url.protocol === "http:" && LOOPBACK_HOSTS.has(url.hostname.toLowerCase()))
  ) {
    throw new Error(
      "Development VITE_API_URL must use HTTPS or an explicit HTTP loopback URL.",
    );
  }

  return configuredUrl.replace(/\/+$/, "");
}
