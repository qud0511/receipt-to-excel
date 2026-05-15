import { useState } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { QueryClientProvider } from "@tanstack/react-query";
import { TopNav } from "@/components/TopNav";
import { DashboardPage } from "@/pages/DashboardPage";
import { UploadPage } from "@/pages/UploadPage";
import { VerifyPage } from "@/pages/VerifyPage";
import { ResultPage } from "@/pages/ResultPage";
import { TemplatesPage } from "@/pages/TemplatesPage";
import { makeQueryClient } from "@/lib/query";
import { REQUIRE_AUTH } from "@/lib/config";

export function App() {
  const [queryClient] = useState(makeQueryClient);

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="flex h-full min-h-screen flex-col bg-bg">
          <TopNav userName={REQUIRE_AUTH ? undefined : "홍길동"} />
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/upload" element={<UploadPage />} />
            <Route path="/verify/:sessionId" element={<VerifyPage />} />
            <Route path="/result/:sessionId" element={<ResultPage />} />
            <Route path="/templates" element={<TemplatesPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
