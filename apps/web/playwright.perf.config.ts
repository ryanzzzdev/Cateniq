import { defineConfig } from "@playwright/test";

// Perf harness: generates the ~100k-point corridor on demand into
// ../.perf-fixtures (gitignored) and serves it via CATENIQ_FIXTURES_DIR.
export default defineConfig({
  testDir: "./e2e",
  testMatch: "perf.spec.ts",
  use: { baseURL: "http://localhost:4174" },
  webServer: [
    {
      command:
        "cd ../../backend && uv run python ../scripts/generate_perf_corridor.py ../.perf-fixtures && CATENIQ_FIXTURES_DIR=../.perf-fixtures uv run uvicorn cateniq.app:app --port 8001",
      url: "http://localhost:8001/api/health",
      reuseExistingServer: !process.env.CI,
    },
    {
      command:
        "npm run build && CATENIQ_API=http://localhost:8001 npm run preview -- --port 4174 --strictPort",
      url: "http://localhost:4174",
      reuseExistingServer: !process.env.CI,
    },
  ],
});
