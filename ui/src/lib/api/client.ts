import { API_BASE } from "@/lib/config";
import type { AppError } from "./types";

export class ApiError extends Error {
  status: number;
  detail: string;
  code: string | undefined;
  failedTxIds: number[] | undefined;
  constructor(status: number, body: Partial<AppError> & { detail?: string }) {
    super(body.detail ?? `HTTP ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.detail = body.detail ?? "";
    this.code = body.code;
    this.failedTxIds = body.failed_tx_ids;
  }
}

interface ApiFetchOptions {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown;
  signal?: AbortSignal;
  headers?: Record<string, string>;
  /** multipart 업로드 시 FormData 그대로 사용 (body 미사용) */
  formData?: FormData;
}

function makeCorrelationId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export async function apiFetch<T = unknown>(path: string, opts: ApiFetchOptions = {}): Promise<T> {
  const { method = "GET", body, signal, headers, formData } = opts;
  const url = `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;

  const init: RequestInit = {
    method,
    signal,
    headers: {
      "X-Correlation-Id": makeCorrelationId(),
      Accept: "application/json",
      ...headers,
    },
    credentials: "include",
  };

  if (formData) {
    init.body = formData;
  } else if (body !== undefined) {
    (init.headers as Record<string, string>)["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }

  const res = await fetch(url, init);

  if (res.status === 204) return undefined as T;

  const contentType = res.headers.get("Content-Type") ?? "";
  const isJson = contentType.includes("application/json");

  if (!res.ok) {
    const errBody = isJson ? ((await res.json()) as Partial<AppError>) : { detail: await res.text() };
    throw new ApiError(res.status, errBody);
  }

  if (!isJson) return (await res.blob()) as T;
  return (await res.json()) as T;
}

export function downloadUrl(path: string): string {
  return `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;
}
