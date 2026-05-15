import { setupServer } from "msw/node";
import { http, HttpResponse } from "msw";

/**
 * MSW handler 카탈로그.
 * 24 endpoint mock 은 Phase 7.3 부터 채워짐 — 본 setup 단계는 healthz 만 mock.
 */
export const handlers = [
  http.get("/healthz", () => HttpResponse.json({ status: "ok" })),
  http.get("/api/healthz", () => HttpResponse.json({ status: "ok" })),
];

export const server = setupServer(...handlers);
