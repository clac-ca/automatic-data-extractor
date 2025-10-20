import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { HydratedRouter } from "react-router/dom";

const container = document.getElementById("root");

if (!container) {
  throw new Error("Root element missing");
}

createRoot(container).render(
  <StrictMode>
    <HydratedRouter />
  </StrictMode>,
);
