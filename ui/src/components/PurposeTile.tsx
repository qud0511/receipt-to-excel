import { cn } from "@/lib/cn";
import { PURPOSE_ICONS, type Purpose } from "@/lib/constants";

interface PurposeTileProps {
  purpose: Purpose;
  active?: boolean;
  onSelect?: (purpose: Purpose) => void;
  className?: string;
}

export function PurposeTile({ purpose, active, onSelect, className }: PurposeTileProps) {
  return (
    <button
      type="button"
      onClick={() => onSelect?.(purpose)}
      aria-pressed={active}
      className={cn(
        "flex flex-col items-center justify-center gap-1 rounded-lg border px-2 py-2.5 text-[12.5px] font-medium transition-colors",
        active
          ? "border-brand-border bg-brand-soft text-brand"
          : "border-border bg-surface text-text-2 hover:border-brand-border hover:bg-brand-soft/40",
        className,
      )}
    >
      <span className="text-base leading-none" aria-hidden>
        {PURPOSE_ICONS[purpose]}
      </span>
      <span>{purpose}</span>
    </button>
  );
}
