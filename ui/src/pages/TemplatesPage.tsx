import { useEffect, useState } from "react";
import { Button } from "@/components/Button";
import { Icon } from "@/components/Icon";
import { TemplateList } from "@/features/templates/TemplateList";
import { TemplateGrid } from "@/features/templates/TemplateGrid";
import { MappingChips } from "@/features/templates/MappingChips";
import { DropZone } from "@/features/upload/DropZone";
import { useTemplates } from "@/lib/hooks/useTemplates";
import {
  useAnalyzeTemplate,
  useCreateTemplate,
  useDeleteTemplate,
  useTemplateGrid,
} from "@/lib/hooks/useTemplateGrid";
import { templateRawUrl } from "@/lib/api/templates";
import type { SheetConfigView } from "@/lib/api/types";
import { ApiError } from "@/lib/api/client";

export function TemplatesPage() {
  const templates = useTemplates();
  const [activeId, setActiveId] = useState<number | null>(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [newName, setNewName] = useState("");

  const analyze = useAnalyzeTemplate();
  const create = useCreateTemplate();
  const del = useDeleteTemplate();
  const grid = useTemplateGrid(activeId);

  // 첫 진입 시 default 또는 첫 항목 선택
  useEffect(() => {
    if (templates.data && activeId == null && templates.data.length > 0) {
      const def = templates.data.find((t) => t.is_default) ?? templates.data[0];
      if (def) setActiveId(def.id);
    }
  }, [templates.data, activeId]);

  const active = templates.data?.find((t) => t.id === activeId) ?? null;
  // 첫 시트의 mapping 정보 (Field/Category 양식 모두 공통 노출)
  const firstSheet: SheetConfigView | null = null;

  function handleAnalyzeFile(files: File[]) {
    const f = files[0];
    if (!f) return;
    setFile(f);
    if (!newName) setNewName(f.name.replace(/\.xlsx$/i, ""));
    analyze.mutate(f);
  }

  function submitCreate() {
    if (!file || !newName) return;
    create.mutate(
      { file, name: newName },
      {
        onSuccess: (resp) => {
          setActiveId(resp.template_id);
          setUploadOpen(false);
          setFile(null);
          setNewName("");
          analyze.reset();
        },
      },
    );
  }

  function handleDelete() {
    if (active == null) return;
    if (!window.confirm(`'${active.name}' 템플릿을 삭제할까요? 되돌릴 수 없습니다.`)) return;
    del.mutate(active.id, {
      onSuccess: () => setActiveId(null),
    });
  }

  const createError = create.error instanceof ApiError ? create.error.detail : null;

  return (
    <section className="flex h-full flex-1 min-h-0">
      <TemplateList
        items={templates.data ?? []}
        activeId={activeId}
        onSelect={setActiveId}
        onUpload={() => setUploadOpen(true)}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        {active ? (
          <>
            <header className="flex items-center gap-3 border-b border-border bg-surface px-5 py-3.5">
              <h2 className="text-[15px] font-bold">{active.name}</h2>
              <span
                className={
                  active.mapping_status === "mapped"
                    ? "rounded bg-success-soft px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-success"
                    : "rounded bg-conf-medium/15 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-conf-medium"
                }
              >
                {active.mapping_status === "mapped" ? "매핑 완료" : "매핑 필요"}
              </span>
              <div className="ml-auto flex items-center gap-2">
                <a
                  href={templateRawUrl(active.id)}
                  download
                  className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-border bg-surface px-4 text-[13px] font-medium text-text-2 hover:bg-surface-2"
                >
                  <Icon name="Download" /> 양식만 받기
                </a>
                <Button variant="ghost" size="md" onClick={handleDelete} disabled={del.isPending}>
                  <Icon name="Close" /> 삭제
                </Button>
              </div>
            </header>

            {grid.data && firstSheet ? <MappingChips sheet={firstSheet} /> : null}
            {grid.isLoading ? (
              <div className="grid flex-1 place-items-center text-[13px] text-text-3">불러오는 중...</div>
            ) : grid.data ? (
              <TemplateGrid grid={grid.data} />
            ) : (
              <div className="grid flex-1 place-items-center text-[13px] text-text-3">
                양식 grid 를 불러오지 못했습니다.
              </div>
            )}
          </>
        ) : (
          <div className="grid flex-1 place-items-center bg-bg p-8 text-center">
            <div>
              <h2 className="mb-2 text-[16px] font-bold">템플릿이 없습니다</h2>
              <p className="mb-4 text-[13px] text-text-3">
                회사별 지출결의서 양식(.xlsx) 을 등록해 주세요.
              </p>
              <Button onClick={() => setUploadOpen(true)}>
                <Icon name="Plus" /> 양식 업로드
              </Button>
            </div>
          </div>
        )}
      </div>

      {uploadOpen && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/40">
          <div className="w-[560px] max-w-[90%] overflow-hidden rounded-2xl bg-surface shadow-lg">
            <div className="flex items-center justify-between border-b border-border px-5 py-3.5">
              <div className="text-[15px] font-bold">템플릿 업로드</div>
              <button
                onClick={() => {
                  setUploadOpen(false);
                  setFile(null);
                  setNewName("");
                  analyze.reset();
                }}
                aria-label="닫기"
              >
                <Icon name="Close" />
              </button>
            </div>
            <div className="space-y-3.5 p-5">
              {!file ? (
                <DropZone accept=".xlsx" onFiles={handleAnalyzeFile} />
              ) : (
                <>
                  <div className="rounded-md border border-border bg-bg p-3 text-[13px]">
                    📎 <strong>{file.name}</strong>
                    {analyze.isPending && <span className="ml-2 text-text-3">분석 중...</span>}
                    {analyze.data && (
                      <span className="ml-2 text-success">
                        분석 완료 · 시트 {Object.keys(analyze.data.sheets).length}개 ·
                        {" "}
                        {analyze.data.mapping_status === "mapped" ? "매핑 자동 완료" : "매핑 필요"}
                      </span>
                    )}
                  </div>
                  <div>
                    <label className="mb-1.5 block text-[11.5px] font-semibold text-text-3">템플릿 이름</label>
                    <input
                      value={newName}
                      onChange={(e) => setNewName(e.target.value)}
                      placeholder="예: A사 파견용 양식"
                      className="h-9 w-full rounded-md border border-border bg-bg px-2.5"
                    />
                  </div>
                </>
              )}
              {createError && <div className="text-[12px] text-conf-low">{createError}</div>}
            </div>
            <div className="flex justify-end gap-2 border-t border-border bg-surface-2 px-5 py-3">
              <Button
                variant="ghost"
                onClick={() => {
                  setUploadOpen(false);
                  setFile(null);
                  setNewName("");
                  analyze.reset();
                }}
              >
                취소
              </Button>
              <Button onClick={submitCreate} disabled={!file || !newName || create.isPending}>
                {create.isPending ? "등록 중..." : "등록"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
