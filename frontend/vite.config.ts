import { defineConfig } from "vitest/config";
import { loadEnv } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, process.cwd(), "VITE_");
  if (command === "build") {
    const base = env.VITE_API_BASE_URL;
    if (!base)
      throw new Error("VITE_API_BASE_URL is required for production builds");
    const url = new URL(base);
    if (
      !["http:", "https:"].includes(url.protocol) ||
      url.username ||
      url.password ||
      url.search ||
      url.hash
    )
      throw new Error(
        "VITE_API_BASE_URL must be an HTTP(S) URL without credentials, query or fragment",
      );
  }
  return {
    plugins: [react()],
    server: { port: 3000, strictPort: true },
    preview: { port: 3000, strictPort: true },
    test: {
      environment: "jsdom",
      setupFiles: ["./src/test/setup.ts"],
      clearMocks: true,
    },
  };
});
