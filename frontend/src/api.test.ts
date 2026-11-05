import { describe, expect, it, vi } from "vitest";
import { apiFetch } from "./api";

describe("apiFetch", () => {
  it("sends credentials and parses API JSON", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify({ ok: true }), {
            status: 200,
            headers: { "content-type": "application/json" },
          }),
        ),
    );
    await expect(apiFetch<{ ok: boolean }>("/health")).resolves.toEqual({
      ok: true,
    });
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining("/health"),
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("surfaces the backend error message", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(
            JSON.stringify({ error: { message: "Blocked by policy" } }),
            { status: 409, headers: { "content-type": "application/json" } },
          ),
        ),
    );
    await expect(apiFetch("/exports")).rejects.toThrow("Blocked by policy");
  });
});
