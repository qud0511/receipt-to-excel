import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { subscribeSession } from "./sse";

interface MockEventSourceInstance {
  url: string;
  readyState: number;
  close: ReturnType<typeof vi.fn>;
  onmessage: ((ev: MessageEvent) => void) | null;
  onerror: ((ev: Event) => void) | null;
  onopen: ((ev: Event) => void) | null;
  __dispatch: (data: string) => void;
}

let lastInstance: MockEventSourceInstance | null = null;

class MockEventSource implements MockEventSourceInstance {
  url: string;
  readyState = 0;
  onmessage: ((ev: MessageEvent) => void) | null = null;
  onerror: ((ev: Event) => void) | null = null;
  onopen: ((ev: Event) => void) | null = null;
  close = vi.fn(() => {
    this.readyState = 2;
  });
  constructor(url: string) {
    this.url = url;
    // eslint-disable-next-line @typescript-eslint/no-this-alias -- 테스트 mock 인프라
    lastInstance = this;
  }
  __dispatch(data: string) {
    this.onmessage?.(new MessageEvent("message", { data }));
  }
}

beforeEach(() => {
  vi.stubGlobal("EventSource", MockEventSource);
  lastInstance = null;
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("subscribeSession", () => {
  it("/api/sessions/{id}/stream URL 로 EventSource 생성", () => {
    subscribeSession(7, { onEvent: () => {} });
    expect(lastInstance?.url).toBe("/api/sessions/7/stream");
  });

  it("수신 메시지를 SSEMessage 로 파싱하여 onEvent 호출", () => {
    const onEvent = vi.fn();
    subscribeSession(1, { onEvent });
    lastInstance?.__dispatch(
      JSON.stringify({
        stage: "ocr",
        file_idx: 1,
        total: 3,
        filename: "r.pdf",
        msg: "OCR 진행 중",
        tx_id: null,
      }),
    );
    expect(onEvent).toHaveBeenCalledWith(
      expect.objectContaining({ stage: "ocr", file_idx: 1, total: 3 }),
    );
  });

  it("done 이벤트 시 자동 close", () => {
    subscribeSession(2, { onEvent: () => {} });
    lastInstance?.__dispatch(
      JSON.stringify({ stage: "done", file_idx: 3, total: 3, filename: "", msg: "완료", tx_id: null }),
    );
    expect(lastInstance?.close).toHaveBeenCalled();
  });

  it("반환된 cleanup 호출 시 close", () => {
    const stop = subscribeSession(3, { onEvent: () => {} });
    stop();
    expect(lastInstance?.close).toHaveBeenCalled();
  });
});
