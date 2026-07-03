"use client";

import { useEffect } from "react";
import { initAnalytics } from "@/lib/analytics";

// Drop-in replacement for Vercel's <Analytics />. Initialising Firebase
// Analytics fires the automatic `page_view` for the initial load; the app is a
// single-page SPA, so that one init covers pageview reporting.
export function FirebaseAnalytics() {
  useEffect(() => {
    void initAnalytics();
  }, []);
  return null;
}
