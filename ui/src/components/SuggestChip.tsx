import { cn } from "@/lib/cn";

interface SuggestChipProps {
  label: string;
  recent?: boolean;
  active?: boolean;
  onPick?: (label: string) => void;
  className?: string;
}

export function SuggestChip({ label, recent, active, onPick, className }: SuggestChipProps) {
  return (
    <button
      type="button"
      onClick={() => onPick?.(label)}
      aria-pressed={active}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[12.5px] font-medium transition-colors",
        active
          ? "border-brand-border bg-brand-soft text-brand"
          : "border-border bg-surface text-text-2 hover:border-brand-border hover:bg-brand-soft/50",
        className,
      )}
    >
      {recent && (
        <span className="rounded bg-brand px-1 py-0.5 text-[9px] font-bold uppercase tracking-wider text-white">
          최근
        </span>
      )}
      {label}
    </button>
  );
}
