import { memo, useEffect, useRef, useState } from "react";
import { cn } from "@/lib/cn";
import type { TransactionView, TransactionPatchRequest } from "@/lib/api/types";
import { formatDateDot, formatKRWshort } from "@/lib/format";
import { ConfidenceBadge, type Confidence } from "@/components/ConfidenceBadge";

interface VerifyGridProps {
  rows: TransactionView[];
  selected: Set<number>;
  activeId: number | null;
  onToggleSelect?: (txId: number, next: boolean) => void;
  onActivate?: (txId: number) => void;
  onPatch?: (txId: number, patch: TransactionPatchRequest) => void;
  onToggleSelectAll?: (next: boolean) => void;
}

const HEAD = [
  { key: "check", label: "" },
  { key: "conf", label: "AI신뢰도" },
  { key: "date", label: "일시" },
  { key: "merchant", label: "가맹점" },
  { key: "category", label: "분류" },
  { key: "vendor", label: "거래처" },
  { key: "project", label: "프로젝트" },
  { key: "purpose", label: "용도" },
  { key: "headcount", label: "인원" },
  { key: "amount", label: "금액" },
] as const;

function confidenceTone(score: number): Confidence {
  if (score >= 0.8) return "high";
  if (score >= 0.6) return "medium";
  if (score > 0) return "low";
  return "none";
}

function rowStatus(t: TransactionView): "missing" | "review" | "complete" {
  const requiredMissing = !t.vendor || !t.purpose;
  if (requiredMissing) return "missing";
  const hasLowField = Object.values(t.field_confidence).some((c) => c === "low" || c === "none");
  if (hasLowField || t.confidence_score < 0.6) return "review";
  return "complete";
}

const STATUS_LABEL = { missing: "필수 누락", review: "재확인 필요", complete: "완료" } as const;
const STATUS_TONE = {
  missing: "bg-conf-low/10 text-conf-low",
  review: "bg-conf-medium/15 text-conf-medium",
  complete: "bg-success-soft text-success",
} as const;

interface CellInputProps {
  value: string;
  placeholder: string;
  onCommit: (next: string) => void;
}

const CellInput = memo(function CellInput({ value, placeholder, onCommit }: CellInputProps) {
  const [v, setV] = useState(value);
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => setV(value), [value]);
  return (
    <input
      ref={ref}
      value={v}
      placeholder={placeholder}
      onChange={(e) => setV(e.target.value)}
      onBlur={() => {
        if (v !== value) onCommit(v);
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter") (e.currentTarget as HTMLInputElement).blur();
        if (e.key === "Escape") {
          setV(value);
          (e.currentTarget as HTMLInputElement).blur();
        }
      }}
      className="h-9 w-full bg-transparent px-2.5 text-[13px] outline-none focus:bg-surface focus:shadow-[inset_0_0_0_2px_var(--brand)]"
    />
  );
});

export function VerifyGrid({
  rows,
  selected,
  activeId,
  onToggleSelect,
  onActivate,
  onPatch,
  onToggleSelectAll,
}: VerifyGridProps) {
  const allSelected = rows.length > 0 && rows.every((r) => selected.has(r.id));
  return (
    <div className="flex-1 overflow-auto">
      <table className="w-full border-separate border-spacing-0 text-[12.5px]">
        <thead>
          <tr>
            {HEAD.map((h) => (
              <th
                key={h.key}
                className={cn(
                  "sticky top-0 z-10 border-b border-r border-border bg-surface-2 px-2.5 py-2 text-left text-[10.5px] font-semibold uppercase tracking-wider text-text-3",
                  h.key === "check" && "w-9 text-center",
                  h.key === "amount" && "text-right",
                )}
              >
                {h.key === "check" ? (
                  <input
                    type="checkbox"
                    aria-label="전체 선택"
                    checked={allSelected}
                    onChange={(e) => onToggleSelectAll?.(e.target.checked)}
                  />
                ) : (
                  h.label
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((t) => {
            const status = rowStatus(t);
            const isActive = activeId === t.id;
            const isSelected = selected.has(t.id);
            return (
              <tr
                key={t.id}
                onClick={(e) => {
                  // 체크박스/input click 은 부모 row 클릭으로 보지 않음
                  const tag = (e.target as HTMLElement).tagName;
                  if (tag !== "INPUT" && tag !== "BUTTON") onActivate?.(t.id);
                }}
                className={cn(
                  "cursor-pointer transition-colors",
                  isSelected && "selected",
                  isActive && "active",
                  "hover:bg-surface-2",
                )}
              >
                <td
                  className={cn(
                    "h-10 border-b border-r border-border bg-surface text-center align-middle",
                    isSelected && "bg-brand-soft",
                    isActive && !isSelected && "bg-[oklch(0.97_0.025_80)]",
                  )}
                >
                  <input
                    type="checkbox"
                    data-row-id={t.id}
                    aria-label={`${t.가맹점명} 선택`}
                    checked={isSelected}
                    onChange={(e) => onToggleSelect?.(t.id, e.target.checked)}
                  />
                </td>
                <td className={cn("h-10 border-b border-r border-border align-middle", isSelected && "bg-brand-soft")}>
                  <div className="flex items-center justify-center gap-1">
                    <ConfidenceBadge level={confidenceTone(t.confidence_score)} dotOnly />
                    <span className="num text-[11px] font-bold">{Math.round(t.confidence_score * 100)}%</span>
                  </div>
                </td>
                <td className={cn("h-10 border-b border-r border-border px-2.5 align-middle text-text-2", isSelected && "bg-brand-soft")}>
                  <div className="num text-[11.5px]">{formatDateDot(t.거래일)}</div>
                  <div className="num text-[10.5px] text-text-3">{t.거래시각 ?? ""}</div>
                </td>
                <td className={cn("h-10 border-b border-r border-border px-2.5 align-middle font-medium", isSelected && "bg-brand-soft")}>
                  {t.가맹점명}
                </td>
                <td className={cn("h-10 border-b border-r border-border px-2.5 align-middle text-text-3", isSelected && "bg-brand-soft")}>
                  {t.업종 ?? "—"}
                </td>
                <td className={cn("h-10 border-b border-r border-border align-middle", isSelected && "bg-brand-soft")}>
                  <CellInput
                    value={t.vendor ?? ""}
                    placeholder="거래처 입력"
                    onCommit={(v) => onPatch?.(t.id, { vendor: v || null })}
                  />
                </td>
                <td className={cn("h-10 border-b border-r border-border align-middle", isSelected && "bg-brand-soft")}>
                  <CellInput
                    value={t.project ?? ""}
                    placeholder="프로젝트"
                    onCommit={(v) => onPatch?.(t.id, { project: v || null })}
                  />
                </td>
                <td className={cn("h-10 border-b border-r border-border align-middle", isSelected && "bg-brand-soft")}>
                  <CellInput
                    value={t.purpose ?? ""}
                    placeholder="용도"
                    onCommit={(v) => onPatch?.(t.id, { purpose: v || null })}
                  />
                </td>
                <td className={cn("h-10 border-b border-r border-border align-middle text-center", isSelected && "bg-brand-soft")}>
                  <input
                    type="number"
                    min={1}
                    value={t.headcount ?? ""}
                    onChange={(e) => {
                      const n = Number(e.target.value);
                      onPatch?.(t.id, { headcount: Number.isFinite(n) && n > 0 ? n : null });
                    }}
                    className="num h-9 w-12 bg-transparent text-center outline-none focus:bg-surface focus:shadow-[inset_0_0_0_2px_var(--brand)]"
                  />
                </td>
                <td className={cn("h-10 border-b border-r border-border px-2.5 align-middle text-right", isSelected && "bg-brand-soft")}>
                  <div className="num font-bold">{formatKRWshort(t.금액)}</div>
                  <span
                    className={cn(
                      "mt-0.5 inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-semibold",
                      STATUS_TONE[status],
                    )}
                  >
                    {STATUS_LABEL[status]}
                  </span>
                </td>
              </tr>
            );
          })}
          {rows.length === 0 && (
            <tr>
              <td colSpan={HEAD.length} className="px-4 py-12 text-center text-[13px] text-text-3">
                표시할 거래가 없습니다.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
