import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const apiProxy = { "/api": "http://localhost:8000" };

export default defineConfig({
  plugins: [react()],
  server: { proxy: apiProxy },
  preview: { proxy: apiProxy },
  test: { environment: "node" },
});
