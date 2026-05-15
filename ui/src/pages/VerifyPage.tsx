import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Button } from "@/components/Button";
import { Icon } from "@/components/Icon";
import { ReceiptPane } from "@/features/verify/ReceiptPane";
import { VerifyGrid } from "@/features/verify/VerifyGrid";
import { FilterChips } from "@/features/verify/FilterChips";
import { BulkBar } from "@/features/verify/BulkBar";
import { SummaryBar } from "@/features/verify/SummaryBar";
import { useTransactions, useBulkTag, usePatchTransaction } from "@/lib/hooks/useTransactions";
import { useVendors } from "@/lib/hooks/useVendors";
import { useProjects } from "@/lib/hooks/useProjects";
import { useTeamGroups } from "@/lib/hooks/useTeamGroups";
import { AttendeesModal } from "@/features/verify/AttendeesModal";
import type { VerifyFilter } from "@/lib/constants";
import { ApiError } from "@/lib/api/client";
import type { AutocompleteOption } from "@/components/Autocomplete";

export function VerifyPage() {
  const { sessionId: sidParam } = useParams<{ sessionId: string }>();
  const sessionId = Number(sidParam);
  const nav = useNavigate();
  const [filter, setFilter] = useState<VerifyFilter>("all");
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [activeId, setActiveId] = useState<number | null>(null);
  const [activeProjectVendorId, setActiveProjectVendorId] = useState<number | null>(null);
  const [attendeesEditId, setAttendeesEditId] = useState<number | null>(null);

  const list = useTransactions(sessionId, filter);
  const patch = usePatchTransaction(sessionId);
  const bulk = useBulkTag(sessionId);
  const vendors = useVendors("");
  const projects = useProjects(activeProjectVendorId);
  const teamGroups = useTeamGroups();

  const rows = useMemo(() => list.data?.transactions ?? [], [list.data]);
  const counts = list.data?.counts ?? { all: 0, missing: 0, review: 0, complete: 0 };
  const active = useMemo(() => rows.find((r) => r.id === activeId) ?? rows[0] ?? null, [rows, activeId]);
  const activeIdx = active ? rows.findIndex((r) => r.id === active.id) : -1;

  const vendorOptions: AutocompleteOption[] = useMemo(
    () =>
      (vendors.data ?? []).map((v, i) => ({
        value: v.name,
        recent: i < 3 && v.last_used_at != null,
        meta: v.usage_count > 0 ? `${v.usage_count}회` : undefined,
      })),
    [vendors.data],
  );
  const projectOptions: AutocompleteOption[] = useMemo(
    () =>
      (projects.data ?? []).map((p, i) => ({
        value: p.name,
        recent: i < 3 && p.last_used_at != null,
        meta: p.usage_count > 0 ? `${p.usage_count}회` : undefined,
      })),
    [projects.data],
  );
  const vendorIdByName = useMemo(() => {
    const m: Record<string, number> = {};
    for (const v of vendors.data ?? []) m[v.name] = v.id;
    return m;
  }, [vendors.data]);

  function handleProjectFocus(txId: number) {
    const row = rows.find((r) => r.id === txId);
    if (!row?.vendor) {
      setActiveProjectVendorId(null);
      return;
    }
    const id = vendorIdByName[row.vendor];
    setActiveProjectVendorId(id ?? null);
  }

  const sumAmount = rows.reduce((s, r) => s + r.금액, 0);
  const completed = counts.complete ?? 0;

  function toggleSelect(id: number, next: boolean) {
    setSelected((prev) => {
      const n = new Set(prev);
      if (next) n.add(id);
      else n.delete(id);
      return n;
    });
  }

  function toggleSelectAll(next: boolean) {
    if (!next) {
      setSelected(new Set());
      return;
    }
    setSelected(new Set(rows.map((r) => r.id)));
  }

  function onPrev() {
    if (activeIdx > 0) {
      const prev = rows[activeIdx - 1];
      if (prev) setActiveId(prev.id);
    }
  }
  function onNext() {
    if (activeIdx >= 0 && activeIdx < rows.length - 1) {
      const nxt = rows[activeIdx + 1];
      if (nxt) setActiveId(nxt.id);
    }
  }

  function applyBulk(patchPayload: Parameters<typeof bulk.mutate>[0]["patch"]) {
    bulk.mutate(
      { transaction_ids: Array.from(selected), patch: patchPayload },
      {
        onSuccess: () => setSelected(new Set()),
      },
    );
  }

  const bulkError = bulk.error instanceof ApiError ? bulk.error.detail || `오류 ${bulk.error.status}` : null;

  if (Number.isNaN(sessionId)) {
    return <section className="flex-1 p-6">잘못된 세션 ID 입니다.</section>;
  }

  return (
    <section className="flex h-full flex-1 min-h-0 flex-col">
      <div className="flex items-center gap-3 border-b border-border bg-surface px-4 py-2.5">
        <FilterChips current={filter} counts={counts} onChange={setFilter} />
        <div className="ml-auto flex items-center gap-2">
          <Link to={`/result/${sessionId}`}>
            <Button variant="primary">
              <Icon name="Download" /> 완료하고 다운로드
            </Button>
          </Link>
        </div>
      </div>
      <BulkBar
        count={selected.size}
        isPending={bulk.isPending}
        error={bulkError}
        onApply={applyBulk}
        onClear={() => setSelected(new Set())}
      />

      <div className="flex min-h-0 flex-1">
        <ReceiptPane
          sessionId={sessionId}
          active={active}
          index={activeIdx < 0 ? 0 : activeIdx}
          total={rows.length}
          onPrev={onPrev}
          onNext={onNext}
        />
        <div className="flex min-w-0 flex-1 flex-col">
          {list.isLoading ? (
            <div className="grid flex-1 place-items-center text-[13px] text-text-3">불러오는 중...</div>
          ) : list.error ? (
            <div className="grid flex-1 place-items-center text-[13px] text-conf-low">
              거래 list 를 불러오지 못했습니다.
              <Button variant="ghost" size="sm" className="ml-3" onClick={() => nav(-1)}>
                돌아가기
              </Button>
            </div>
          ) : (
            <VerifyGrid
              rows={rows}
              selected={selected}
              activeId={active?.id ?? null}
              onToggleSelect={toggleSelect}
              onActivate={(id) => setActiveId(id)}
              onPatch={(txId, p) => patch.mutate({ txId, patch: p })}
              onToggleSelectAll={toggleSelectAll}
              vendorOptions={vendorOptions}
              projectOptions={projectOptions}
              onProjectFocus={handleProjectFocus}
              onAttendeesClick={(id) => setAttendeesEditId(id)}
            />
          )}
        </div>
      </div>

      <SummaryBar total={rows.length} completed={completed} sumAmount={sumAmount} />

      <AttendeesModal
        open={attendeesEditId != null}
        initial={rows.find((r) => r.id === attendeesEditId)?.attendees ?? []}
        groups={teamGroups.data ?? []}
        onClose={() => setAttendeesEditId(null)}
        onSave={(next) => {
          if (attendeesEditId != null) {
            patch.mutate({ txId: attendeesEditId, patch: { attendees: next } });
          }
          setAttendeesEditId(null);
        }}
      />
    </section>
  );
}
