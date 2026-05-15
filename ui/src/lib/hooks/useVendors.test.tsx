import { describe, expect, it } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { server } from "@/test/handlers";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { PropsWithChildren } from "react";
import { useVendors } from "./useVendors";

function wrapper(qc: QueryClient) {
  const Wrap = ({ children }: PropsWithChildren) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
  Wrap.displayName = "TestQueryWrapper";
  return Wrap;
}

describe("useVendors", () => {
  it("GET /vendors?q= 응답을 반환", async () => {
    server.use(
      http.get("/api/vendors", ({ request }) => {
        const q = new URL(request.url).searchParams.get("q") ?? "";
        return HttpResponse.json([{ id: 1, name: `${q}회사`, last_used_at: null, usage_count: 3 }]);
      }),
    );
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { result } = renderHook(() => useVendors("신용"), { wrapper: wrapper(qc) });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.[0]?.name).toBe("신용회사");
  });

  it("staleTime 5분 — 같은 query 재호출 시 추가 fetch 없음", async () => {
    let calls = 0;
    server.use(
      http.get("/api/vendors", () => {
        calls += 1;
        return HttpResponse.json([]);
      }),
    );
    const qc = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const w = wrapper(qc);

    const first = renderHook(() => useVendors("a"), { wrapper: w });
    await waitFor(() => expect(first.result.current.isSuccess).toBe(true));
    expect(calls).toBe(1);

    const second = renderHook(() => useVendors("a"), { wrapper: w });
    await waitFor(() => expect(second.result.current.isSuccess).toBe(true));
    expect(calls).toBe(1); // staleTime 안이라 캐시 hit
  });
});
