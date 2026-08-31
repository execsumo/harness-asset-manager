import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

function normalizeBase(value: string | undefined, fallback: string): string {
  const trimmed = (value ?? fallback).trim();
  if (trimmed === "" || trimmed === "/") {
    return "";
  }
  return trimmed.endsWith("/") ? trimmed.slice(0, -1) : trimmed;
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "");
  const apiOrigin = env.VITE_API_ORIGIN ?? "http://127.0.0.1:8000";
  const apiBase = normalizeBase(env.VITE_API_BASE, "/api");
  const devToken = env.VITE_API_TOKEN || env.HARNESSAM_API_TOKEN || "";

  return {
    root: "frontend",
    define: {
      "import.meta.env.VITE_API_TOKEN": JSON.stringify(devToken),
    },
    plugins: [react()],
    server: {
      host: "127.0.0.1",
      port: 5173,
      strictPort: true,
      proxy:
        apiBase === ""
          ? undefined
          : {
              [apiBase]: {
                target: apiOrigin,
                changeOrigin: true,
              },
            },
    },
    build: {
      outDir: "dist",
      emptyOutDir: true,
    },
    test: {
      environment: "jsdom",
      globals: true,
      testTimeout: 10000,
      setupFiles: ["./src/test/setup.ts"],
      include: ["src/**/*.test.{ts,tsx}"],
      coverage: {
        provider: "v8",
        reporter: ["text", "json-summary", "lcov"],
        include: ["src/**/*.{ts,tsx}"],
        exclude: [
          "src/**/*.test.{ts,tsx}",
          "src/test/**",
          "src/api/generated.ts",
          "src/main.tsx",
        ],
        thresholds: {
          statements: 60,
          branches: 55,
          functions: 55,
          lines: 60,
        },
      },
    },
  };
});
