import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwind from "@tailwindcss/vite";
import { resolveApiBase } from "./src/lib/apiBase";

export default defineConfig(({ command, mode }) => {
  if (command === "build") {
    const configuredApiUrl = Object.prototype.hasOwnProperty.call(
      process.env,
      "VITE_API_URL",
    )
      ? process.env.VITE_API_URL
      : loadEnv(mode, process.cwd(), "VITE_API_URL").VITE_API_URL;
    resolveApiBase(configuredApiUrl, true);
  }

  return {
    plugins: [react(), tailwind()],
    server: { proxy: { "/api": "http://localhost:8000" } },
  };
});
