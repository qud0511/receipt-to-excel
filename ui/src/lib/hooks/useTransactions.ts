import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { bulkTag, getTransactions, patchTransaction } from "@/lib/api/sessions";
import type { BulkTagRequest, TransactionListResponse, TransactionPatchRequest } from "@/lib/api/types";
import type { VerifyFilter } from "@/lib/constants";
import { QUERY_STALE } from "@/lib/query";

export function useTransactions(sessionId: number, filter: VerifyFilter) {
  return useQuery({
    queryKey: ["sessions", sessionId, "transactions", filter],
    queryFn: () => getTransactions(sessionId, filter),
    staleTime: QUERY_STALE.transactions,
    enabled: !Number.isNaN(sessionId),
  });
}

export function usePatchTransaction(sessionId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ txId, patch }: { txId: number; patch: TransactionPatchRequest }) =>
      patchTransaction(sessionId, txId, patch),
    onMutate: async ({ txId, patch }) => {
      await qc.cancelQueries({ queryKey: ["sessions", sessionId, "transactions"] });
      const snapshots = qc.getQueriesData<TransactionListResponse>({
        queryKey: ["sessions", sessionId, "transactions"],
      });
      for (const [key, prev] of snapshots) {
        if (!prev) continue;
        qc.setQueryData<TransactionListResponse>(key, {
          ...prev,
          transactions: prev.transactions.map((t) =>
            t.id === txId ? { ...t, ...patch, attendees: patch.attendees ?? t.attendees } : t,
          ),
        });
      }
      return { snapshots };
    },
    onError: (_err, _vars, ctx) => {
      if (!ctx) return;
      for (const [key, prev] of ctx.snapshots) {
        qc.setQueryData(key, prev);
      }
    },
    onSettled: () => qc.invalidateQueries({ queryKey: ["sessions", sessionId, "transactions"] }),
  });
}

export function useBulkTag(sessionId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: BulkTagRequest) => bulkTag(sessionId, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sessions", sessionId, "transactions"] }),
  });
}
