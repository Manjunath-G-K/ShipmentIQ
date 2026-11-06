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

export const API_BASE = (
  import.meta.env.VITE_API_BASE_URL || defaultApiBase()
).replace(/\/$/, "");

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

function csrfToken(): string | undefined {
  const name = import.meta.env.VITE_CSRF_COOKIE_NAME || "shipmentiq_csrf";
  const item = document.cookie
    .split("; ")
    .find((part) => part.startsWith(`${name}=`));
  return item ? decodeURIComponent(item.slice(name.length + 1)) : undefined;
}

export async function apiFetch<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const method = (init.method || "GET").toUpperCase();
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  if (method !== "GET" && method !== "HEAD") {
    const token = csrfToken();
    if (token)
      headers.set(
        import.meta.env.VITE_CSRF_HEADER_NAME || "X-CSRF-Token",
        token,
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
