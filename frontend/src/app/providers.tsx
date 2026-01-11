"use client";

import { QueryProvider } from "@/lib/query";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { Toaster } from "react-hot-toast";
import type { ReactNode } from "react";

export function Providers({ children }: { children: ReactNode }) {
  return (
    <QueryProvider>
      <ErrorBoundary>
        {children}
      </ErrorBoundary>
      <Toaster
        position="bottom-right"
        toastOptions={{
          style: {
            background: "#1a1a1a",
            color: "#e5e5e5",
            border: "1px solid #2a2a2a",
          },
          success: {
            iconTheme: {
              primary: "#5BA37C",
              secondary: "#1a1a1a",
            },
          },
          error: {
            iconTheme: {
              primary: "#D46A6A",
              secondary: "#1a1a1a",
            },
          },
        }}
      />
    </QueryProvider>
  );
}
