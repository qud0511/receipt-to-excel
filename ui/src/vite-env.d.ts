/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE?: string;
  readonly VITE_REQUIRE_AUTH?: string;
  readonly VITE_AAD_TENANT_ID?: string;
  readonly VITE_AAD_CLIENT_ID?: string;
  readonly VITE_AAD_REDIRECT_URI?: string;
  /** "true" 면 dev MSW worker 활성 (백엔드 없이 mock 데이터로 UI 풀 사용) */
  readonly VITE_USE_MOCK?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
