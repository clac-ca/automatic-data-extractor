import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { AppProviders } from "./app/AppProviders";
import { AppRouter } from "./app/AppRouter";
import "./index.css";

const container = document.getElementById("root");

if (!container) {
  throw new Error("Root element missing");
}

createRoot(container).render(
  <StrictMode>
    <AppProviders>
      <AppRouter />
    </AppProviders>
  </StrictMode>,
);
