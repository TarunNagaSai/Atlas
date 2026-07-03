"use client";

// Firebase Analytics wrapper. Exposes a `track(name, params?)` function that
// mirrors the signature of the old `@vercel/analytics` `track`, so call sites
// only had to swap their import path.
//
// Analytics is browser-only and lazily initialised on first use. If the
// Firebase env vars are absent (e.g. local dev) or the browser doesn't support
// Analytics, `track` becomes a no-op instead of throwing.

import { initializeApp, getApps, getApp } from "firebase/app";
import {
  getAnalytics,
  isSupported,
  logEvent,
  type Analytics,
} from "firebase/analytics";

const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
  measurementId: process.env.NEXT_PUBLIC_FIREBASE_MEASUREMENT_ID,
};

// Cached across calls: resolves once to the Analytics instance, or null when
// analytics is unavailable (SSR, unsupported browser, or missing config).
let analyticsPromise: Promise<Analytics | null> | null = null;

export function initAnalytics(): Promise<Analytics | null> {
  if (typeof window === "undefined") return Promise.resolve(null);
  if (!firebaseConfig.apiKey || !firebaseConfig.measurementId) {
    return Promise.resolve(null);
  }
  if (!analyticsPromise) {
    analyticsPromise = isSupported()
      .then((supported) => {
        if (!supported) return null;
        const app = getApps().length ? getApp() : initializeApp(firebaseConfig);
        return getAnalytics(app);
      })
      .catch(() => null);
  }
  return analyticsPromise;
}

// Param value types Firebase accepts on custom events.
export type AnalyticsParams = Record<string, string | number | boolean | undefined>;

export function track(eventName: string, params?: AnalyticsParams): void {
  void initAnalytics().then((analytics) => {
    if (analytics) logEvent(analytics, eventName, params);
  });
}
