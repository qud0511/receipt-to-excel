import { useParams } from "react-router-dom";

export function ResultPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  return (
    <section className="flex-1 overflow-y-auto p-6">
      <header className="mb-4">
        <h1 className="text-[20px] font-bold tracking-tight">지출결의서 완성</h1>
        <p className="mt-1 text-[13px] text-text-3">세션 #{sessionId}</p>
      </header>
      <p className="text-[13px] text-text-3">다운로드 카드 4종 + 통계 — Phase 7.8 채워질 예정</p>
    </section>
  );
}
