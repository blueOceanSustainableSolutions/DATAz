import "@/styles/main.scss";
import "maplibre-gl/dist/maplibre-gl.css";

import React from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "@/context/ThemeProvider";
import { TimezoneProvider } from "@/context/TimezoneProvider";
import App from "@/App";
import { PAGE_TITLE } from "@/config";

document.title = PAGE_TITLE;

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 60 * 1000 } },
});

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <TimezoneProvider>
          <App />
        </TimezoneProvider>
      </ThemeProvider>
    </QueryClientProvider>
  </React.StrictMode>,
);
