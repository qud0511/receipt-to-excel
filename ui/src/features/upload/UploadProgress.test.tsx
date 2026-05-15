import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { UploadProgress } from "./UploadProgress";

describe("UploadProgress", () => {
  it("uploaded stage 메시지 한국어", () => {
    render(<UploadProgress events={[{ stage: "uploaded", file_idx: 0, total: 3, filename: "a.pdf", msg: "", tx_id: null }]} />);
    expect(screen.getAllByText(/업로드 수신/).length).toBeGreaterThan(0);
  });

  it("ocr/llm/rule_based/resolved stage 한국어 매핑", () => {
    render(
      <UploadProgress
        events={[
          { stage: "ocr", file_idx: 1, total: 3, filename: "a.pdf", msg: "", tx_id: null },
          { stage: "llm", file_idx: 1, total: 3, filename: "a.pdf", msg: "", tx_id: null },
          { stage: "rule_based", file_idx: 2, total: 3, filename: "b.pdf", msg: "", tx_id: null },
          { stage: "resolved", file_idx: 2, total: 3, filename: "b.pdf", msg: "", tx_id: 100 },
        ]}
      />,
    );
    expect(screen.getAllByText(/OCR/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/AI/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/규칙 기반/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/추출 완료/).length).toBeGreaterThan(0);
  });

  it("진행률 % 계산 (file_idx/total)", () => {
    render(<UploadProgress events={[{ stage: "ocr", file_idx: 2, total: 4, filename: "x", msg: "", tx_id: null }]} />);
    expect(screen.getByText(/50%/)).toBeInTheDocument();
  });

  it("done stage 시 '완료' 표시 + 100%", () => {
    render(<UploadProgress events={[{ stage: "done", file_idx: 3, total: 3, filename: "", msg: "완료", tx_id: null }]} />);
    expect(screen.getAllByText(/완료/).length).toBeGreaterThan(0);
    expect(screen.getByText(/100%/)).toBeInTheDocument();
  });
});
