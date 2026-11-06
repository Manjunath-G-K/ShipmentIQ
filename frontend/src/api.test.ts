import { afterEach, describe, expect, it, vi } from "vitest";
import {
  API_BASE,
  apiFetch,
  clearCsrfToken,
  resolveApiBase,
} from "./api";

afterEach(() => {
  clearCsrfToken();
  vi.restoreAllMocks();
});

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

  it("bootstraps CSRF in memory and sends it with authenticated writes", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(
          new Response(JSON.stringify({ csrf_token: "csrf-token" }), {
            status: 200,
            headers: { "content-type": "application/json" },
          }),
        )
        .mockResolvedValueOnce(
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
    const [, shipmentRequest] = vi.mocked(fetch).mock.calls[1] as [
      string,
      RequestInit,
    ];
    const headers = new Headers(shipmentRequest.headers);
    expect(url).toContain("/auth/csrf");
    expect(vi.mocked(fetch).mock.calls[1][0]).toContain("/shipments");
    expect(shipmentRequest.credentials).toBe("include");
    expect(headers.get("Content-Type")).toBe("application/json");
    expect(headers.get("X-CSRF-Token")).toBe("csrf-token");
  });

  it.each([
    ["confirmation", "/fields/field-1/confirm", "POST"],
    ["correction", "/fields/field-1", "PATCH"],
    ["rejection", "/fields/field-1/reject", "POST"],
  ])("sends CSRF credentials for %s requests", async (_label, path, method) => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(
          new Response(JSON.stringify({ csrf_token: "csrf-token" }), {
            status: 200,
            headers: { "content-type": "application/json" },
          }),
        )
        .mockResolvedValueOnce(
          new Response(JSON.stringify({ ok: true }), {
            status: 200,
            headers: { "content-type": "application/json" },
          }),
        ),
    );

    await apiFetch(path, {
      method,
      body: JSON.stringify({ expected_version: 1 }),
    });

    const [url, request] = vi.mocked(fetch).mock.calls[1] as [
      string,
      RequestInit,
    ];
    const headers = new Headers(request.headers);
    expect(url).toContain(path);
    expect(request.credentials).toBe("include");
    expect(headers.get("X-CSRF-Token")).toBe("csrf-token");
  });

  it("does not bootstrap CSRF before login", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ id: "user-1" }), {
          status: 200,
          headers: { "content-type": "application/json" },
        }),
      ),
    );

    await apiFetch("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email: "user@example.test", password: "password" }),
    });

    expect(fetch).toHaveBeenCalledTimes(1);
    expect(vi.mocked(fetch).mock.calls[0][0]).toContain("/auth/login");
  });

  it("uses the browser localhost hostname for the default API base", () => {
    expect(API_BASE).toBe(`http://${window.location.hostname}:8000/api/v1`);
  });

  it("normalizes a loopback API override to the browser hostname", () => {
    expect(resolveApiBase("http://127.0.0.1:8000/api/v1")).toBe(
      "http://localhost:8000/api/v1",
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
