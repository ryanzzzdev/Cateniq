import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchHealth } from "./api";

afterEach(() => vi.unstubAllGlobals());

describe("fetchHealth", () => {
  it("returns the parsed health payload", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response('{"status":"ok","service":"cateniq"}')),
    );
    await expect(fetchHealth()).resolves.toEqual({
      status: "ok",
      service: "cateniq",
    });
  });

  it("throws on a non-OK response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("nope", { status: 503 })),
    );
    await expect(fetchHealth()).rejects.toThrow("503");
  });
});
