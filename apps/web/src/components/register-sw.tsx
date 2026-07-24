"use client";

import { useEffect } from "react";

/** PWA skeleton: registers /sw.js. The service worker itself only precaches
 * the shell for now — offline caching of fetched drill questions is Phase 2. */
export function RegisterServiceWorker() {
  useEffect(() => {
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js").catch((err) => {
        console.warn("service worker registration failed", err);
      });
    }
  }, []);
  return null;
}
