import { describe, expect, it, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "@/test/handlers";
import { apiFetch, ApiError } from "./client";

describe("apiFetch", () => {
  it("GET 응답을 JSON 파싱한다", async () => {
    server.use(
      http.get("/api/ping", () => HttpResponse.json({ pong: true })),
    );
    const result = await apiFetch<{ pong: boolean }>("/ping");
    expect(result).toEqual({ pong: true });
  });

  it("모든 요청에 X-Correlation-Id 헤더를 자동으로 붙인다", async () => {
    const received = vi.fn();
    server.use(
      http.get("/api/echo", ({ request }) => {
        received(request.headers.get("X-Correlation-Id"));
        return HttpResponse.json({});
      }),
    );
    await apiFetch("/echo");
    expect(received).toHaveBeenCalledOnce();
    const cid = received.mock.calls[0]?.[0];
    expect(cid).toMatch(/^[0-9a-f-]{36}$/);
  });

  it("401 응답은 ApiError(401) 로 throw", async () => {
    server.use(
      http.get("/api/secure", () =>
        HttpResponse.json({ detail: "권한 없음" }, { status: 401 }),
      ),
    );
    await expect(apiFetch("/secure")).rejects.toMatchObject({
      status: 401,
      detail: "권한 없음",
    });
  });

  it("422 응답은 ApiError + detail 노출", async () => {
    server.use(
      http.post("/api/form", () =>
        HttpResponse.json({ detail: "template_id 미선택" }, { status: 422 }),
      ),
    );
    await expect(apiFetch("/form", { method: "POST", body: {} })).rejects.toBeInstanceOf(ApiError);
  });

  it("body 객체를 JSON.stringify 하여 보낸다", async () => {
    const captured = vi.fn();
    server.use(
      http.post("/api/save", async ({ request }) => {
        captured(await request.json());
        return HttpResponse.json({ ok: true });
      }),
    );
    await apiFetch("/save", { method: "POST", body: { vendor: "신용정보원" } });
    expect(captured).toHaveBeenCalledWith({ vendor: "신용정보원" });
  });
});
