import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { HttpWallClient, type WallClient } from "./api/client";
import "./index.css";

async function makeClient(): Promise<WallClient> {
  // `pnpm dev` then open /?mock to see the wall without a backend.
  if (import.meta.env.DEV && new URLSearchParams(location.search).has("mock")) {
    const { MockWallClient } = await import("./api/mockClient");
    return new MockWallClient();
  }
  return new HttpWallClient();
}

if (import.meta.env.PROD && "serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  });
}

const root = document.getElementById("root");
if (root) {
  void makeClient().then((client) =>
    createRoot(root).render(
      <StrictMode>
        <App client={client} />
      </StrictMode>,
    ),
  );
}
