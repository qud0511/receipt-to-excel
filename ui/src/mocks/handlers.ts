/** dev MSW handlers — VITE_USE_MOCK=true 일 때 활성화. */
import { http, HttpResponse, delay } from "msw";
import {
  MOCK_ATTENDEES,
  MOCK_DASHBOARD,
  MOCK_GENERATE,
  MOCK_GRID,
  MOCK_PROJECTS_BY_VENDOR,
  MOCK_SESSION_STATS,
  MOCK_TEAM_GROUPS,
  MOCK_TEMPLATES,
  MOCK_VENDORS,
  mockTransactions,
} from "./data";

/** dev MSW handlers. e2e/_mocks.ts 와 별도 (Playwright 는 page.route() 패턴). */
export const handlers = [
  // Auth
  http.get("/api/auth/config", () =>
    HttpResponse.json({ require_auth: false, tenant_id: null, client_id: null }),
  ),
  http.get("/api/auth/me", () =>
    HttpResponse.json({ oid: "mock-user-oid", name: "홍길동", email: "honggildong@example.com" }),
  ),

  // Dashboard
  http.get("/api/dashboard/summary", () => HttpResponse.json(MOCK_DASHBOARD)),

  // Templates
  http.get("/api/templates", () => HttpResponse.json(MOCK_TEMPLATES)),
  http.get("/api/templates/:id/grid", () => HttpResponse.json(MOCK_GRID)),
  http.post("/api/templates/analyze", async () => {
    await delay(800);
    return HttpResponse.json({
      sheets: MOCK_GRID.sheets,
      mapping_status: "mapped",
    });
  }),
  http.post("/api/templates", async () => {
    await delay(500);
    return HttpResponse.json({ template_id: 99, name: "신규 업로드 양식", mapping_status: "mapped" });
  }),
  http.patch("/api/templates/:id/cells", () => HttpResponse.json({})),
  http.patch("/api/templates/:id/mapping", () => HttpResponse.json({})),
  http.patch("/api/templates/:id", () => HttpResponse.json({})),
  http.delete("/api/templates/:id", () => new HttpResponse(null, { status: 204 })),

  // Sessions
  http.post("/api/sessions", async () => {
    await delay(400);
    return HttpResponse.json({ session_id: 1, status: "parsing" }, { status: 201 });
  }),
  http.get("/api/sessions/:id/transactions", ({ request }) => {
    const filter = new URL(request.url).searchParams.get("status") ?? "all";
    return HttpResponse.json(mockTransactions(filter));
  }),
  http.patch("/api/sessions/:id/transactions/:tx_id", async () => {
    await delay(150);
    return HttpResponse.json({});
  }),
  http.post("/api/sessions/:id/transactions/bulk-tag", async () => {
    await delay(300);
    return HttpResponse.json({ updated_count: 3 });
  }),
  http.get("/api/sessions/:id/preview-xlsx", () => HttpResponse.json({ sheets: {} })),
  http.post("/api/sessions/:id/generate", async () => {
    await delay(600);
    return HttpResponse.json(MOCK_GENERATE);
  }),
  http.get("/api/sessions/:id/stats", () => HttpResponse.json(MOCK_SESSION_STATS)),

  // Autocomplete
  http.get("/api/vendors", ({ request }) => {
    const q = new URL(request.url).searchParams.get("q") ?? "";
    const list = q ? MOCK_VENDORS.filter((v) => v.name.includes(q)) : MOCK_VENDORS;
    return HttpResponse.json(list);
  }),
  http.get("/api/projects", ({ request }) => {
    const vid = Number(new URL(request.url).searchParams.get("vendor_id") ?? "0");
    return HttpResponse.json(MOCK_PROJECTS_BY_VENDOR[vid] ?? []);
  }),
  http.get("/api/attendees", ({ request }) => {
    const q = new URL(request.url).searchParams.get("q") ?? "";
    const list = q ? MOCK_ATTENDEES.filter((a) => a.name.includes(q)) : MOCK_ATTENDEES;
    return HttpResponse.json(list);
  }),
  http.get("/api/team-groups", () => HttpResponse.json(MOCK_TEAM_GROUPS)),

  // SSE — dev MSW 는 ReadableStream 응답으로 mock
  http.get("/api/sessions/:id/stream", () => {
    const stream = new ReadableStream({
      async start(controller) {
        const enc = new TextEncoder();
        const send = (data: object) => {
          controller.enqueue(enc.encode(`data: ${JSON.stringify(data)}\n\n`));
        };
        controller.enqueue(enc.encode("retry: 60000\n\n"));
        send({ stage: "uploaded", file_idx: 0, total: 3, filename: null, msg: "업로드 수신 — 영수증 3", tx_id: null });
        await new Promise((r) => setTimeout(r, 400));
        for (let i = 1; i <= 3; i += 1) {
          send({ stage: "rule_based", file_idx: i, total: 3, filename: `receipt-${i}.pdf`, msg: "파싱 중", tx_id: null });
          await new Promise((r) => setTimeout(r, 400));
        }
        send({ stage: "done", file_idx: 3, total: 3, filename: null, msg: "완료", tx_id: null });
        controller.close();
      },
    });
    return new HttpResponse(stream, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        Connection: "keep-alive",
      },
    });
  }),
];
