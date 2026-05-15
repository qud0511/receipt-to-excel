import { useRef, useState, type DragEvent } from "react";
import { cn } from "@/lib/cn";
import { Icon } from "@/components/Icon";

interface DropZoneProps {
  onFiles: (files: File[]) => void;
  accept?: string;
  disabled?: boolean;
}

const DEFAULT_ACCEPT = "image/jpeg,image/png,application/pdf,.xlsx,.csv";

export function DropZone({ onFiles, accept = DEFAULT_ACCEPT, disabled }: DropZoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [hover, setHover] = useState(false);

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setHover(false);
    if (disabled) return;
    const files = Array.from(e.dataTransfer?.files ?? []);
    if (files.length > 0) onFiles(files);
  }

  function handleClick() {
    if (disabled) return;
    inputRef.current?.click();
  }

  return (
    <div
      aria-label="업로드 영역"
      role="button"
      tabIndex={0}
      onClick={handleClick}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          handleClick();
        }
      }}
      onDragOver={(e) => {
        e.preventDefault();
        setHover(true);
      }}
      onDragLeave={() => setHover(false)}
      onDrop={handleDrop}
      className={cn(
        "rounded-2xl border-2 border-dashed p-14 text-center transition-colors cursor-pointer",
        hover ? "border-brand bg-brand-soft" : "border-brand-border bg-surface",
        disabled && "cursor-not-allowed opacity-50",
      )}
    >
      <div className="mx-auto mb-4 grid h-16 w-16 place-items-center rounded-2xl bg-brand-soft text-brand">
        <Icon name="Upload" size={28} />
      </div>
      <div className="mb-1 text-[18px] font-bold">파일을 여기로 드래그하세요</div>
      <div className="text-[13px] text-text-3">또는 클릭해서 선택 · PNG, JPG, PDF, XLSX, CSV · 최대 50MB</div>
      <input
        ref={inputRef}
        type="file"
        multiple
        accept={accept}
        data-testid="dropzone-input"
        className="hidden"
        onChange={(e) => {
          const files = Array.from(e.target.files ?? []);
          if (files.length > 0) onFiles(files);
          e.target.value = "";
        }}
      />
    </div>
  );
}
