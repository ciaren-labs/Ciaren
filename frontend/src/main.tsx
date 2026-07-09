import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import { TooltipProvider } from "@/components/ui/tooltip";
import App from "./App";
import { queryClient } from "./lib/queryClient";
import "./index.css";

const rootElement = document.getElementById("root");
if (!rootElement) {
  // The bundle loaded but its mount point is gone — a broken index.html or a
  // stale cached shell. Fail loudly with a readable message instead of a bare
  // "Cannot read properties of null" from a non-null assertion.
  throw new Error('Ciaren could not start: no #root element was found in the page.');
}

ReactDOM.createRoot(rootElement).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <TooltipProvider delayDuration={200} skipDelayDuration={300}>
          <App />
        </TooltipProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
);
