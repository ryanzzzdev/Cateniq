import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const apiTarget = process.env.CATENIQ_API ?? "http://localhost:8000";
const apiProxy = { "/api": apiTarget };

export default defineConfig({
  plugins: [react()],
  server: { proxy: apiProxy },
  preview: { proxy: apiProxy },
  test: { environment: "node", exclude: ["e2e/**", "node_modules/**"] },
});
