import { useEffect } from "react";
import { Link, useParams } from "react-router-dom";
import { Button } from "@/components/Button";
import { Icon } from "@/components/Icon";
import { DownloadCard } from "@/features/result/DownloadCard";
import { useGenerate, useSessionStats } from "@/lib/hooks/useSessionStats";
import { downloadArtifactUrl } from "@/lib/api/sessions";

function formatDuration(s: number): string {
  const m = Math.floor(s / 60);
  const r = Math.round(s % 60);
  if (m === 0) return `${r}초`;
  if (r === 0) return `${m}분`;
  return `${m}분 ${r}초`;
}

export function ResultPage() {
  const { sessionId: sidParam } = useParams<{ sessionId: string }>();
  const sessionId = Number(sidParam);
  const stats = useSessionStats(sessionId);
  const gen = useGenerate(sessionId);

  // 화면 진입 시 1회 generate 시도 (이미 생성된 경우 백엔드가 idempotent 응답 가정)
  useEffect(() => {
    if (!Number.isNaN(sessionId) && !gen.isPending && !gen.data && !gen.error) {
      gen.mutate();
    }
  }, [sessionId, gen]);

  if (Number.isNaN(sessionId)) {
    return <section className="flex-1 p-6">잘못된 세션 ID 입니다.</section>;
  }

  const month = new Date().getMonth() + 1;
  const year = new Date().getFullYear();
  const baseName = `${year}_${String(month).padStart(2, "0")}_지출결의서`;

  const time = stats.data ? formatDuration(stats.data.processing_time_s) : null;
  const saved = stats.data ? Math.max(0, stats.data.time_saved_s) : null;

  return (
    <section className="flex flex-1 items-start justify-center overflow-y-auto bg-bg p-8">
      <article className="w-full max-w-[720px] overflow-hidden rounded-2xl border border-border bg-surface shadow-md">
        <header className="border-b border-border bg-gradient-to-b from-brand-soft to-transparent px-10 py-8 text-center">
          <div className="mx-auto mb-3.5 grid h-14 w-14 place-items-center rounded-full bg-brand text-white shadow-lg">
            <Icon name="Check" size={24} />
          </div>
          <h1 className="text-[22px] font-bold tracking-tight">지출결의서 완성</h1>
          <p className="mt-1.5 text-[13px] text-text-3">
            AI 자동 추출 + 자동 합계 포함. 아래에서 다운로드하세요.
          </p>
        </header>

        <div className="space-y-3 p-7">
          {gen.isError ? (
            <div className="rounded-xl border border-conf-low/40 bg-conf-low/5 p-3 text-[13px] text-conf-low">
              생성 중 오류가 발생했습니다. 검수 화면에서 누락 항목을 확인하세요.
            </div>
          ) : (
            <>
              <DownloadCard
                kind="xlsx"
                name={`${baseName}.xlsx`}
                desc="지출결의서 — 자동 합계 포함"
                href={downloadArtifactUrl(sessionId, "xlsx")}
                primary
              />
              <DownloadCard
                kind="layout_pdf"
                name={`증빙_영수증_합본_${year}_${String(month).padStart(2, "0")}.pdf`}
                desc="A4 모아찍기 — 영수증 layout PDF"
                href={downloadArtifactUrl(sessionId, "layout_pdf")}
              />
              <DownloadCard
                kind="merged_pdf"
                name={`증빙_원본_${year}_${String(month).padStart(2, "0")}.pdf`}
                desc="원본 PDF 합본 (raw merged)"
                href={downloadArtifactUrl(sessionId, "merged_pdf")}
              />
              <DownloadCard
                kind="zip"
                name={`${baseName}_bundle.zip`}
                desc="XLSX + PDF 한 번에 받기"
                href={downloadArtifactUrl(sessionId, "zip")}
                primary
              />
              <button
                type="button"
                disabled
                className="flex w-full items-center gap-3.5 rounded-xl border border-border bg-surface p-4 text-left opacity-60"
              >
                <div className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-surface-2 text-text-3">
                  ✉
                </div>
                <div className="flex-1">
                  <div className="text-[14px] font-semibold">팀장님께 메일로 보내기</div>
                  <div className="text-[12px] text-text-3">Phase 7+ 예정 — 외부 메일 연동 후 활성화</div>
                </div>
              </button>
            </>
          )}
        </div>

        <footer className="flex items-center justify-between gap-4 border-t border-border bg-surface-2 px-7 py-4 text-[12px] text-text-3">
          <div>
            {time && saved != null ? (
              <>
                처리 시간 <strong className="num text-text">{time}</strong> · 평소 대비{" "}
                <strong className="num text-success">{formatDuration(saved)}</strong> 단축
              </>
            ) : (
              "처리 통계를 불러오는 중..."
            )}
          </div>
          <Link to={`/verify/${sessionId}`}>
            <Button variant="ghost" size="sm">
              검수 화면으로
            </Button>
          </Link>
        </footer>
      </article>
    </section>
  );
}
