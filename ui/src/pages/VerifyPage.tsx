import { useParams } from "react-router-dom";

export function VerifyPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  return (
    <section className="flex-1 overflow-y-auto p-6">
      <header className="mb-4">
        <h1 className="text-[20px] font-bold tracking-tight">검수 · 수정</h1>
        <p className="mt-1 text-[13px] text-text-3">세션 #{sessionId}</p>
      </header>
      <p className="text-[13px] text-text-3">
        split view · 그리드 · TaggingForm · 일괄 적용 — Phase 7.7 채워질 예정
      </p>
    </section>
  );
}
