import { describe, expect, it } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { server } from "@/test/handlers";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { PropsWithChildren } from "react";
import { useProjects } from "./useProjects";

function wrapper(qc: QueryClient) {
  const Wrap = ({ children }: PropsWithChildren) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
  Wrap.displayName = "TestQueryWrapper";
  return Wrap;
}

describe("useProjects", () => {
  it("vendor_id 미설정이면 disabled (fetch X)", async () => {
    let calls = 0;
    server.use(
      http.get("/api/projects", () => {
        calls += 1;
        return HttpResponse.json([]);
      }),
    );
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    renderHook(() => useProjects(null), { wrapper: wrapper(qc) });
    // 잠시 대기
    await new Promise((r) => setTimeout(r, 50));
    expect(calls).toBe(0);
  });

  it("vendor_id 있으면 GET /projects?vendor_id=X", async () => {
    server.use(
      http.get("/api/projects", ({ request }) => {
        const vid = new URL(request.url).searchParams.get("vendor_id");
        return HttpResponse.json([{ id: 1, vendor_id: Number(vid), name: `P-${vid}`, last_used_at: null, usage_count: 1 }]);
      }),
    );
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { result } = renderHook(() => useProjects(7), { wrapper: wrapper(qc) });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.[0]?.name).toBe("P-7");
  });
});
