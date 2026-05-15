import { API_BASE } from "@/lib/config";
import type { SSEMessage } from "@/lib/api/types";

interface SubscribeOptions {
  onEvent: (msg: SSEMessage) => void;
  onError?: (event: Event) => void;
  onOpen?: () => void;
}

/**
 * /sessions/{id}/stream SSE 구독. done/error 스테이지 수신 시 자동 close.
 * 반환된 cleanup 함수를 useEffect 의 unmount 에서 호출.
 */
export function subscribeSession(sessionId: number, opts: SubscribeOptions): () => void {
  const url = `${API_BASE}/sessions/${sessionId}/stream`;
  const es = new EventSource(url, { withCredentials: true });

  es.onopen = () => opts.onOpen?.();
  es.onerror = (ev) => opts.onError?.(ev);
  es.onmessage = (ev) => {
    try {
      const parsed = JSON.parse((ev as MessageEvent<string>).data) as SSEMessage;
      opts.onEvent(parsed);
      if (parsed.stage === "done" || parsed.stage === "error") {
        es.close();
      }
    } catch {
      // 잘못된 payload 는 무시 (백엔드 디리미터/JSON 보장).
    }
  };

  return () => es.close();
}
