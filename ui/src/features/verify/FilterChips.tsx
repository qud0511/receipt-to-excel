import { cn } from "@/lib/cn";
import { VERIFY_FILTERS, VERIFY_FILTER_LABEL, type VerifyFilter } from "@/lib/constants";

interface FilterChipsProps {
  current: VerifyFilter;
  counts: Record<VerifyFilter, number>;
  onChange: (next: VerifyFilter) => void;
  className?: string;
}

export function FilterChips({ current, counts, onChange, className }: FilterChipsProps) {
  return (
    <div className={cn("flex items-center gap-1.5", className)}>
      {VERIFY_FILTERS.map((key) => {
        const active = key === current;
        return (
          <button
            key={key}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(key)}
            className={cn(
              "inline-flex h-8 items-center gap-1.5 rounded-md px-3 text-[12.5px] font-medium transition-colors",
              active
                ? "border border-brand-border bg-brand-soft text-brand"
                : "border border-transparent bg-bg text-text-2 hover:bg-surface-2",
            )}
          >
            {VERIFY_FILTER_LABEL[key]}
            <span
              className={cn(
                "num rounded px-1.5 py-0.5 text-[10px] font-bold",
                active ? "bg-brand text-white" : "bg-surface-2 text-text-3",
              )}
            >
              {counts[key] ?? 0}
            </span>
          </button>
        );
      })}
    </div>
  );
}
