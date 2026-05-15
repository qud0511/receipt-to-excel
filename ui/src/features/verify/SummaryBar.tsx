import { cn } from "@/lib/cn";
import { formatKRW } from "@/lib/format";

interface SummaryBarProps {
  total: number;
  completed: number;
  sumAmount: number;
  dueDate?: string;
  today?: Date;
  className?: string;
}

function daysUntil(dueIso: string, today: Date): number {
  const due = new Date(`${dueIso}T00:00:00`);
  const t = new Date(today);
  t.setHours(0, 0, 0, 0);
  due.setHours(0, 0, 0, 0);
  return Math.round((due.getTime() - t.getTime()) / (1000 * 60 * 60 * 24));
}

export function SummaryBar({ total, completed, sumAmount, dueDate, today, className }: SummaryBarProps) {
  const dDays = dueDate ? daysUntil(dueDate, today ?? new Date()) : null;
  const dLabel = dDays == null ? null : dDays >= 0 ? `D-${dDays}` : `D+${-dDays}`;

  return (
    <div
      className={cn(
        "flex items-center gap-6 border-t border-border bg-surface-2 px-4 py-2.5 text-[12.5px] text-text-2",
        className,
      )}
    >
      <span>
        총 <strong className="num text-text">{total}</strong>건
      </span>
      <span>
        입력완료 <strong className="num text-success">{completed}</strong> / {total}
      </span>
      <span>
        합계 <strong className="num text-text">{formatKRW(sumAmount)}</strong>
      </span>
      <span className="ml-auto text-[11px] text-text-3">
        {dueDate ? `정산 마감일까지 ` : null}
        {dLabel && <strong className="num text-text">{dLabel}</strong>}
      </span>
    </div>
  );
}
