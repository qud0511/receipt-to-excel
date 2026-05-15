import { Link } from "react-router-dom";
import { Button } from "@/components/Button";
import { Icon } from "@/components/Icon";
import { KpiCard } from "@/features/dashboard/KpiCard";
import { RecentList } from "@/features/dashboard/RecentList";
import { useDashboardSummary } from "@/lib/hooks/useDashboardSummary";
import { formatDeltaPct, formatKRW, formatKRWshort } from "@/lib/format";

export function DashboardPage() {
  const { data, isLoading, error } = useDashboardSummary();

  return (
    <section className="flex-1 overflow-y-auto p-6">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-[22px] font-bold tracking-tight">
            안녕하세요, <span className="text-brand">{data?.user_name ?? "사용자"}</span>님
          </h1>
          <p className="mt-1 text-[13px] text-text-3">
            {isLoading
              ? "이번 달 현황을 불러오는 중..."
              : data
                ? `이번 달 결제 ${data.this_month.transaction_count}건 · ${data.this_month.pending_count}건이 미입력 상태입니다.`
                : "현황을 불러오지 못했습니다."}
          </p>
        </div>
        <Link to="/upload">
          <Button>
            <Icon name="Plus" /> 지출결의서 작성
          </Button>
        </Link>
      </header>

      {error ? (
        <div className="rounded-xl border border-conf-low/40 bg-conf-low/5 p-4 text-[13px] text-conf-low">
          요약 데이터를 불러오지 못했습니다.
        </div>
      ) : (
        <>
          <div className="mb-6 grid grid-cols-1 gap-3.5 sm:grid-cols-2 lg:grid-cols-4">
            <KpiCard
              label="이번 달 총 지출"
              value={data ? formatKRW(data.this_month.total_amount) : "—"}
              delta={data ? `전월 대비 ${formatDeltaPct(data.this_month.prev_month_diff_pct)}` : undefined}
              deltaTone={
                data && data.this_month.prev_month_diff_pct >= 0 ? "up" : "down"
              }
            />
            <KpiCard
              label="결제 건수"
              value={data ? formatKRWshort(data.this_month.transaction_count) : "—"}
              delta={
                data && data.this_month.pending_count > 0
                  ? `${data.this_month.pending_count}건 미입력`
                  : undefined
              }
              deltaTone={data && data.this_month.pending_count > 0 ? "down" : "up"}
            />
            <KpiCard
              label="완료된 결의서"
              value={data ? `${data.this_year.completed_count}건` : "—"}
              delta={data ? "올해 누적" : undefined}
            />
            <KpiCard
              label="절약된 시간"
              value={data ? `${data.this_year.time_saved_hours}시간` : "—"}
              delta={data ? "AI 자동 추출 기준" : undefined}
            />
          </div>

          <h2 className="mb-2.5 flex items-center gap-2 text-[13px] font-semibold text-text-2">
            최근 작성한 결의서
          </h2>
          <RecentList items={data?.recent_expense_reports ?? []} />
        </>
      )}
    </section>
  );
}
