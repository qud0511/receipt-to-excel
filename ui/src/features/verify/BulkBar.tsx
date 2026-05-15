import { useState } from "react";
import { Button } from "@/components/Button";
import { Icon } from "@/components/Icon";
import { PURPOSES, type Purpose } from "@/lib/constants";
import type { TransactionPatchRequest } from "@/lib/api/types";

interface BulkBarProps {
  count: number;
  onApply: (patch: TransactionPatchRequest) => void;
  onClear: () => void;
  isPending?: boolean;
  error?: string | null;
}

export function BulkBar({ count, onApply, onClear, isPending, error }: BulkBarProps) {
  const [open, setOpen] = useState(false);
  const [vendor, setVendor] = useState("");
  const [project, setProject] = useState("");
  const [purpose, setPurpose] = useState<Purpose | "">("");

  if (count === 0) return null;

  function submit() {
    const patch: TransactionPatchRequest = {};
    if (vendor) patch.vendor = vendor;
    if (project) patch.project = project;
    if (purpose) patch.purpose = purpose;
    onApply(patch);
    setOpen(false);
  }

  return (
    <>
      <div className="flex items-center gap-2.5 border-b border-brand-border bg-brand-soft px-4 py-2.5 text-[13px]">
        <span>선택됨</span>
        <span className="num rounded border border-brand-border bg-surface px-2 py-0.5 text-[12px] font-bold text-brand">
          {count}
        </span>
        <span className="text-text-3">건에 일괄로</span>
        <Button size="sm" onClick={() => setOpen(true)}>
          <Icon name="Sparkle" /> 일괄 적용
        </Button>
        <button
          type="button"
          onClick={onClear}
          className="ml-auto text-[12px] text-text-3 hover:text-conf-low"
        >
          선택 해제
        </button>
      </div>

      {open && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/40">
          <div className="w-[480px] max-w-[90%] overflow-hidden rounded-2xl bg-surface shadow-lg">
            <div className="flex items-center justify-between border-b border-border px-5 py-3.5">
              <div className="text-[15px] font-bold">일괄 적용 — {count}건</div>
              <button onClick={() => setOpen(false)} aria-label="닫기">
                <Icon name="Close" />
              </button>
            </div>
            <div className="space-y-3.5 p-5">
              <div>
                <label className="mb-1.5 block text-[11.5px] font-semibold text-text-3">거래처</label>
                <input
                  value={vendor}
                  onChange={(e) => setVendor(e.target.value)}
                  placeholder="거래처 입력 (선택)"
                  className="h-9 w-full rounded-md border border-border bg-bg px-2.5"
                />
              </div>
              <div>
                <label className="mb-1.5 block text-[11.5px] font-semibold text-text-3">프로젝트</label>
                <input
                  value={project}
                  onChange={(e) => setProject(e.target.value)}
                  placeholder="프로젝트 입력 (선택)"
                  className="h-9 w-full rounded-md border border-border bg-bg px-2.5"
                />
              </div>
              <div>
                <label className="mb-1.5 block text-[11.5px] font-semibold text-text-3">용도</label>
                <div className="flex flex-wrap gap-1.5">
                  {PURPOSES.map((p) => (
                    <button
                      key={p}
                      type="button"
                      aria-pressed={purpose === p}
                      onClick={() => setPurpose(purpose === p ? "" : p)}
                      className={
                        purpose === p
                          ? "inline-flex items-center rounded-full border border-brand-border bg-brand-soft px-3 py-1 text-[12.5px] font-medium text-brand"
                          : "inline-flex items-center rounded-full border border-border bg-surface px-3 py-1 text-[12.5px] font-medium text-text-2 hover:border-brand-border"
                      }
                    >
                      {p}
                    </button>
                  ))}
                </div>
              </div>
              {error && <div className="text-[12px] text-conf-low">{error}</div>}
            </div>
            <div className="flex justify-end gap-2 border-t border-border bg-surface-2 px-5 py-3">
              <Button variant="ghost" onClick={() => setOpen(false)}>
                취소
              </Button>
              <Button onClick={submit} disabled={isPending || (!vendor && !project && !purpose)}>
                {isPending ? "적용 중..." : "적용"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
