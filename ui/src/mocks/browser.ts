import { setupWorker } from "msw/browser";
import { handlers } from "./handlers";

/**
 * dev MSW worker — VITE_USE_MOCK=true 일 때 main.tsx 에서 lazy import.
 * `public/mockServiceWorker.js` 는 `npx msw init public` 으로 등록됨 (Phase 7.1).
 */
export const worker = setupWorker(...handlers);
