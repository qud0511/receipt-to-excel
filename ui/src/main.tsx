import React from "react";
import ReactDOM from "react-dom/client";
import "./styles/globals.css";
import { App } from "./App";

const rootEl = document.getElementById("root");
if (!rootEl) throw new Error("root element not found");

async function bootstrap() {
  if (import.meta.env.VITE_USE_MOCK === "true") {
    const { worker } = await import("./mocks/browser");
    await worker.start({
      onUnhandledRequest: "bypass",
      serviceWorker: { url: "/mockServiceWorker.js" },
    });
  }
  ReactDOM.createRoot(rootEl!).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  );
}

void bootstrap();
