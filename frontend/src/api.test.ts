import { describe, expect, it, vi } from "vitest";
import { API_BASE, apiFetch } from "./api";

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

  it("reads the CSRF cookie and sends it with authenticated writes", async () => {
    const cookie = vi
      .spyOn(document, "cookie", "get")
      .mockReturnValue("shipmentiq_csrf=csrf-token");
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify({ id: "shipment-1" }), {
            status: 201,
            headers: { "content-type": "application/json" },
          }),
        ),
    );

    await apiFetch<{ id: string }>("/shipments", {
      method: "POST",
      body: JSON.stringify({ shipment_reference: "SHP-TEST" }),
    });

    const [url, request] = vi.mocked(fetch).mock.calls[0] as [
      string,
      RequestInit,
    ];
    const headers = new Headers(request.headers);
    expect(url).toContain("/shipments");
    expect(request.credentials).toBe("include");
    expect(headers.get("Content-Type")).toBe("application/json");
    expect(headers.get("X-CSRF-Token")).toBe("csrf-token");
    cookie.mockRestore();
  });

  it("uses the browser localhost hostname for the default API base", () => {
    expect(API_BASE).toBe(`http://${window.location.hostname}:8000/api/v1`);
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
