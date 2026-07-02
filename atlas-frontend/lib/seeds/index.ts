"use client";

/**
 * Static, bundled demo chats.
 *
 * The DB-seed path (see `hydrateSeeds` in app/page.tsx) can only carry text —
 * the `chats` table stores prompt/answer, and neither localStorage nor the
 * replay path keeps an attachment's bytes. So a demo chat whose point IS an
 * attached image can't ride the DB path. Those live here instead: the transcript
 * is bundled as JSON and the image as a static asset under `public/seeds/`, with
 * the user message's attachment pointing at that asset via its `src`.
 *
 * On load (client storage mode) `hydrateStaticSeeds` writes each of these into
 * localStorage once, so they show in the sidebar and — like any client chat —
 * continue purely client-side from there.
 */

import type { Message } from "@/types";
import { getChatStorageMode } from "@/lib/models/chat";
import { isSeeded, loadLocalChat, markSeeded, saveLocalChat } from "@/lib/local-history";
import compareCompanies from "./compare-companies.json";

interface StaticSeed {
  /** Stable conversation id — reused as the localStorage key + seeded marker. */
  id: string;
  messages: Message[];
}

const STATIC_SEEDS: StaticSeed[] = [
  {
    id: "0db271ab-a7a2-4057-8440-c1d7f9bc7cfe",
    messages: compareCompanies as Message[],
  },
];

/**
 * One-time hydrate of the bundled seeds into localStorage. Client mode only (in
 * DB mode the backend owns history). Idempotent via the seeded-id marker: a seed
 * the visitor later deletes locally isn't re-added, and a seed they've already
 * continued (now larger locally) isn't clobbered. Returns true if it wrote any.
 */
export function hydrateStaticSeeds(): boolean {
  if (getChatStorageMode() !== "client") return false;
  let wrote = false;
  for (const seed of STATIC_SEEDS) {
    if (isSeeded(seed.id) || loadLocalChat(seed.id).length > 0) continue;
    saveLocalChat(seed.id, seed.messages);
    markSeeded(seed.id);
    wrote = true;
  }
  return wrote;
}
