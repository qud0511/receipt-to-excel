import { PublicClientApplication, type Configuration } from "@azure/msal-browser";
import { AAD_CONFIG, REQUIRE_AUTH } from "@/lib/config";

/**
 * MSAL.js SPA flow. REQUIRE_AUTH=false (dev) 면 PCA 가 생성되지만 사용 안 함.
 * 운영 (REQUIRE_AUTH=true) 시 AuthGate 가 unauth 사용자를 loginRedirect 로 보냄.
 */
function buildMsalConfig(): Configuration {
  return {
    auth: {
      clientId: AAD_CONFIG.clientId,
      authority: AAD_CONFIG.tenantId ? `https://login.microsoftonline.com/${AAD_CONFIG.tenantId}` : undefined,
      redirectUri: AAD_CONFIG.redirectUri,
      navigateToLoginRequestUrl: true,
    },
    cache: {
      cacheLocation: "sessionStorage",
      storeAuthStateInCookie: false,
    },
  };
}

let _pca: PublicClientApplication | null = null;

export function getMsalInstance(): PublicClientApplication {
  if (!_pca) {
    _pca = new PublicClientApplication(buildMsalConfig());
  }
  return _pca;
}

export const LOGIN_SCOPES = ["openid", "profile", "email"];

export { REQUIRE_AUTH };
