import { QueryClient } from "@tanstack/react-query";

const FIVE_MIN = 5 * 60 * 1000;

/**
 * TanStack QueryClient — staleTime 차등.
 * 자동완성: 5분 (백엔드도 Cache-Control max-age=300).
 * 동적 데이터 (transactions): hook 에서 staleTime: 0 override.
 */
export function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: 1,
        refetchOnWindowFocus: false,
        staleTime: 60 * 1000, // 디폴트 1분
      },
      mutations: {
        retry: 0,
      },
    },
  });
}

export const QUERY_STALE = {
  autocomplete: FIVE_MIN,
  templates: 60 * 1000,
  dashboard: 30 * 1000,
  transactions: 0,
} as const;
