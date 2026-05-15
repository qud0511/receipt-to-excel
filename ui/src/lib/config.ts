/** 환경 변수 + 정적 상수 단일 진입점. */

export const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";

export const REQUIRE_AUTH = import.meta.env.VITE_REQUIRE_AUTH === "true";

export const AAD_CONFIG = {
  tenantId: import.meta.env.VITE_AAD_TENANT_ID ?? "",
  clientId: import.meta.env.VITE_AAD_CLIENT_ID ?? "",
  redirectUri: import.meta.env.VITE_AAD_REDIRECT_URI ?? window.location.origin,
} as const;
