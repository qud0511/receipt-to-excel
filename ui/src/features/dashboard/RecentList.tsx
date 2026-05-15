import { Link } from "react-router-dom";
import type { RecentExpenseReport } from "@/lib/api/types";
import { StatusPill } from "@/components/StatusPill";
import { formatKRW, formatYearMonth } from "@/lib/format";

interface RecentListProps {
  items: RecentExpenseReport[];
}

export function RecentList({ items }: RecentListProps) {
  if (items.length === 0) {
    return (
      <div className="rounded-xl border border-border bg-surface p-8 text-center text-[13px] text-text-3">
        최근 작성한 결의서가 없습니다.
      </div>
    );
  }

  return (
    <ul className="overflow-hidden rounded-xl border border-border bg-surface">
      {items.map((it) => (
        <li key={it.session_id} className="border-b border-border last:border-b-0">
          <Link
            to={`/verify/${it.session_id}`}
            className="flex items-center gap-3.5 px-4 py-3.5 hover:bg-surface-2"
          >
            <span className="num inline-flex h-9 items-center rounded-md bg-brand-soft px-2.5 text-[14px] font-bold tracking-tighter text-brand">
              {formatYearMonth(it.year_month)}
            </span>
            <div className="min-w-0 flex-1">
              <div className="truncate text-[14px] font-semibold text-text">
                {it.template_name ?? "(양식 없음)"}
              </div>
              <div className="text-[12px] text-text-3">영수증 {it.receipt_count}장</div>
            </div>
            <div className="num text-[15px] font-bold tracking-tight">{formatKRW(it.total_amount)}</div>
            <StatusPill sessionStatus={it.status} />
          </Link>
        </li>
      ))}
    </ul>
  );
}
