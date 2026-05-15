import { describe, expect, it } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { server } from "@/test/handlers";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { PropsWithChildren } from "react";
import { useTemplates } from "./useTemplates";
import type { TemplateSummary } from "@/lib/api/types";

function wrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const Wrap = ({ children }: PropsWithChildren) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
  Wrap.displayName = "TestQueryWrapper";
  return Wrap;
}

describe("useTemplates", () => {
  it("GET /templates 리스트 응답을 반환", async () => {
    const list: TemplateSummary[] = [
      {
        id: 1,
        name: "A사 파견용 양식",
        is_default: true,
        mapping_status: "mapped",
        created_at: "2026-05-10T00:00:00",
        updated_at: "2026-05-15T00:00:00",
      },
    ];
    server.use(http.get("/api/templates", () => HttpResponse.json(list)));
    const { result } = renderHook(() => useTemplates(), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(list);
  });
});
