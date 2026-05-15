import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { Button } from "@/components/Button";
import { Icon } from "@/components/Icon";
import { DropZone } from "@/features/upload/DropZone";
import { UploadProgress } from "@/features/upload/UploadProgress";
import { useTemplates } from "@/lib/hooks/useTemplates";
import { createSession } from "@/lib/api/sessions";
import { subscribeSession } from "@/lib/sse";
import { useUploadStore, classifyFiles } from "@/stores/upload";
import { ApiError } from "@/lib/api/client";

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

function currentYearMonth(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export function UploadPage() {
  const nav = useNavigate();
  const templates = useTemplates();
  const upload = useUploadStore();
  const [templateId, setTemplateId] = useState<number | null>(null);
  const [yearMonth, setYearMonth] = useState(currentYearMonth);
  const [sessionId, setSessionId] = useState<number | null>(null);

  // 템플릿 list 로드 후 default 선택
  useEffect(() => {
    if (templates.data && templateId == null) {
      const def = templates.data.find((t) => t.is_default) ?? templates.data[0];
      if (def) setTemplateId(def.id);
    }
  }, [templates.data, templateId]);

  const create = useMutation({
    mutationFn: createSession,
    onSuccess: ({ session_id }) => {
      setSessionId(session_id);
    },
  });

  // SSE 구독: session 생성 후 → done 시 verify 로 이동
  useEffect(() => {
    if (sessionId == null) return;
    const stop = subscribeSession(sessionId, {
      onEvent: (e) => {
        upload.pushEvent(e);
        if (e.stage === "done") {
          // 약간 텀 두고 이동
          setTimeout(() => nav(`/verify/${sessionId}`), 600);
        }
      },
    });
    return stop;
  }, [sessionId, nav, upload]);

  const fileCount = upload.receipts.length + upload.cardStatements.length;
  const canSubmit = fileCount > 0 && templateId != null && !create.isPending && sessionId == null;

  const errorMessage = useMemo(() => {
    if (!create.error) return null;
    if (create.error instanceof ApiError) return create.error.detail || `오류 (${create.error.status})`;
    return "업로드 중 오류가 발생했습니다.";
  }, [create.error]);

  function handleFiles(files: File[]) {
    const { receipts, cardStatements } = classifyFiles(files);
    if (receipts.length > 0) upload.appendReceipts(receipts);
    if (cardStatements.length > 0) upload.appendCardStatements(cardStatements);
  }

  function handleSubmit() {
    if (!canSubmit || templateId == null) return;
    create.mutate({
      receipts: upload.receipts,
      card_statements: upload.cardStatements,
      year_month: yearMonth,
      template_id: templateId,
    });
  }

  return (
    <section className="flex-1 overflow-y-auto p-6">
      <header className="mb-4">
        <h1 className="text-[20px] font-bold tracking-tight">매출전표 일괄 업로드</h1>
        <p className="mt-1 text-[13px] text-text-3">
          법인카드 사용내역(XLSX/CSV)과 영수증 사진(PNG/JPG/PDF)을 한 번에 올려주세요.
        </p>
      </header>

      <div className="mb-4 flex flex-wrap items-center gap-3 rounded-xl border border-border bg-surface p-3.5 text-[13px]">
        <label className="font-semibold text-text-2">정산월</label>
        <input
          type="month"
          value={yearMonth}
          onChange={(e) => setYearMonth(e.target.value)}
          className="h-8 rounded-md border border-border bg-bg px-2 font-mono"
        />
        <label className="ml-3 font-semibold text-text-2">양식</label>
        <select
          value={templateId ?? ""}
          onChange={(e) => setTemplateId(e.target.value ? Number(e.target.value) : null)}
          className="h-8 min-w-[200px] rounded-md border border-border bg-bg px-2"
          disabled={templates.isLoading || sessionId != null}
        >
          <option value="">{templates.isLoading ? "불러오는 중..." : "선택"}</option>
          {templates.data?.map((t) => (
            <option key={t.id} value={t.id}>
              {t.name} {t.is_default ? "(기본)" : ""}
            </option>
          ))}
        </select>
        {templates.data?.length === 0 && (
          <span className="text-conf-low">먼저 템플릿을 등록하세요.</span>
        )}
      </div>

      {sessionId == null ? (
        <>
          <div className="mb-4">
            <DropZone onFiles={handleFiles} disabled={create.isPending} />
          </div>

          {fileCount > 0 && (
            <div className="mb-4 rounded-xl border border-border bg-surface p-4">
              <div className="mb-2 text-[12px] font-semibold uppercase tracking-wider text-text-3">
                업로드 대기 · {fileCount}개
              </div>
              <ul className="space-y-1.5 text-[13px]">
                {upload.receipts.map((f) => (
                  <li key={`r-${f.name}`} className="flex items-center gap-2">
                    <span className="num inline-flex h-7 w-9 items-center justify-center rounded bg-bg text-[10px] font-bold text-text-2">
                      영수증
                    </span>
                    <span className="flex-1 truncate">{f.name}</span>
                    <span className="num text-[11px] text-text-3">{formatBytes(f.size)}</span>
                    <button
                      className="text-text-3 hover:text-conf-low"
                      onClick={() => upload.removeReceipt(f.name)}
                      aria-label={`${f.name} 제거`}
                    >
                      <Icon name="Close" />
                    </button>
                  </li>
                ))}
                {upload.cardStatements.map((f) => (
                  <li key={`c-${f.name}`} className="flex items-center gap-2">
                    <span className="num inline-flex h-7 w-9 items-center justify-center rounded bg-brand-soft text-[10px] font-bold text-brand">
                      카드
                    </span>
                    <span className="flex-1 truncate">{f.name}</span>
                    <span className="num text-[11px] text-text-3">{formatBytes(f.size)}</span>
                    <button
                      className="text-text-3 hover:text-conf-low"
                      onClick={() => upload.removeCardStatement(f.name)}
                      aria-label={`${f.name} 제거`}
                    >
                      <Icon name="Close" />
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {errorMessage && (
            <div className="mb-4 rounded-xl border border-conf-low/40 bg-conf-low/5 p-3 text-[13px] text-conf-low">
              {errorMessage}
            </div>
          )}

          <div className="flex justify-end">
            <Button onClick={handleSubmit} disabled={!canSubmit}>
              {create.isPending ? "업로드 중..." : "AI 자동 추출 시작"}
            </Button>
          </div>
        </>
      ) : (
        <UploadProgress events={upload.events} />
      )}
    </section>
  );
}
