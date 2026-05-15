import { Link } from "react-router-dom";
import { Button } from "@/components/Button";
import { Icon } from "@/components/Icon";

export function DashboardPage() {
  return (
    <section className="flex-1 overflow-y-auto p-6">
      <header className="mb-6 flex items-end justify-between">
        <div>
          <h1 className="text-[22px] font-bold tracking-tight">대시보드</h1>
          <p className="mt-1 text-[13px] text-text-3">
            이번 달 결제 현황과 최근 작성한 결의서를 한눈에 확인하세요.
          </p>
        </div>
        <Link to="/upload">
          <Button>
            <Icon name="Plus" /> 지출결의서 작성
          </Button>
        </Link>
      </header>

      <p className="text-[13px] text-text-3">KPI · 최근 결의서 list — Phase 7.5 채워질 예정</p>
    </section>
  );
}
