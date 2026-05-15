import { cn } from "@/lib/cn";
import type { SheetConfigView } from "@/lib/api/types";

interface MappingChipsProps {
  sheet: SheetConfigView;
}

const FIELDS: Array<{ key: keyof SheetConfigView; label: string }> = [
  { key: "date_col", label: "거래일" },
  { key: "merchant_col", label: "거래처명" },
  { key: "project_col", label: "프로젝트명" },
  { key: "total_col", label: "금액" },
  { key: "note_col", label: "비고" },
];

export function MappingChips({ sheet }: MappingChipsProps) {
  return (
    <div className="flex items-center gap-2.5 overflow-x-auto border-b border-border bg-surface px-4 py-2.5 text-[12px]">
      <span className="shrink-0 font-semibold text-text-2">필드 매핑</span>
      {FIELDS.map((f) => {
        const col = sheet[f.key] as string | null | undefined;
        const mapped = !!col;
        return (
          <span
            key={f.key}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 whitespace-nowrap",
              mapped
                ? "border-border bg-surface-2 text-text-2"
                : "unmapped border-dashed border-border-strong bg-bg text-text-3 opacity-80",
            )}
          >
            {f.label}
            <span
              className={cn(
                "num rounded px-1.5 py-0.5 text-[10px] font-bold",
                mapped ? "bg-brand-soft text-brand" : "bg-bg text-text-3",
              )}
            >
              {col ?? "—"}
            </span>
          </span>
        );
      })}
      <span className="shrink-0 text-[11px] text-text-3">
        데이터 영역 {sheet.data_start_row}~{sheet.data_end_row} · 헤더 row {sheet.header_row}
      </span>
    </div>
  );
}
