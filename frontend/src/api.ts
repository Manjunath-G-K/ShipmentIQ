const LOCAL_HOSTNAMES = new Set(["localhost", "127.0.0.1"]);

function defaultApiBase(): string {
  if (typeof window === "undefined") return "http://127.0.0.1:8000/api/v1";

  // Keep host-only auth and CSRF cookies readable when the UI is opened on
  // either supported local hostname. A cookie set by localhost is not
  // available to a page running on 127.0.0.1, and vice versa.
  const hostname =
    window.location.hostname === "localhost" ||
    window.location.hostname === "127.0.0.1"
      ? window.location.hostname
      : "127.0.0.1";
  return `${window.location.protocol}//${hostname}:8000/api/v1`;
}

export function resolveApiBase(
  configured = import.meta.env.VITE_API_BASE_URL,
): string {
  if (!configured || typeof window === "undefined") {
    return configured || defaultApiBase();
  }

  // A local API URL is host-specific because the auth and CSRF cookies are
  // host-only. Keep a configured loopback URL on the same hostname as the UI.
  try {
    const configuredUrl = new URL(configured, window.location.origin);
    if (
      LOCAL_HOSTNAMES.has(window.location.hostname) &&
      LOCAL_HOSTNAMES.has(configuredUrl.hostname)
    ) {
      configuredUrl.hostname = window.location.hostname;
      return configuredUrl.toString();
    }
  } catch {
    // Let fetch surface an invalid non-local configuration as before.
  }
  return configured;
}

export const API_BASE = resolveApiBase().replace(/\/$/, "");

export type ApiError = {
  error?: {
    code?: string;
    message?: string;
    details?: { blockers?: Blocker[] };
  };
};
export type Blocker = {
  code: string;
  message: string;
  field_id?: string;
  field_path?: string;
  rule_key?: string;
  document_id?: string;
};

let csrfTokenValue: string | undefined;

export function clearCsrfToken(): void {
  csrfTokenValue = undefined;
}

async function csrfToken(): Promise<string> {
  if (csrfTokenValue) return csrfTokenValue;

  const response = await fetch(`${API_BASE}/auth/csrf`, {
    credentials: "include",
  });
  if (!response.ok) {
    throw new Error(`CSRF bootstrap failed (${response.status})`);
  }
  const payload: unknown = await response.json();
  if (
    typeof payload !== "object" ||
    payload === null ||
    !("csrf_token" in payload) ||
    typeof payload.csrf_token !== "string" ||
    payload.csrf_token.length === 0
  ) {
    throw new Error("CSRF bootstrap returned an invalid token");
  }
  csrfTokenValue = payload.csrf_token;
  return csrfTokenValue;
}

export async function apiFetch<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const method = (init.method || "GET").toUpperCase();
  const headers = new Headers(init.headers);
  if (path === "/auth/login") clearCsrfToken();
  if (init.body && !(init.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  if (method !== "GET" && method !== "HEAD" && path !== "/auth/login") {
    headers.set(
      import.meta.env.VITE_CSRF_HEADER_NAME || "X-CSRF-Token",
      await csrfToken(),
    );
  }
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
    credentials: "include",
  });
  if (!response.ok) {
    let payload: ApiError | undefined;
    try {
      payload = (await response.json()) as ApiError;
    } catch {
      /* non-JSON error */
    }
    throw new Error(
      payload?.error?.message || `Request failed (${response.status})`,
    );
  }
  if (path === "/auth/logout") clearCsrfToken();
  if (response.status === 204) return undefined as T;
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("text/csv")) return (await response.text()) as T;
  return (await response.json()) as T;
}

export async function apiBlob(path: string): Promise<Blob> {
  const response = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
  });
  if (!response.ok)
    throw new Error(`Document request failed (${response.status})`);
  return response.blob();
}
