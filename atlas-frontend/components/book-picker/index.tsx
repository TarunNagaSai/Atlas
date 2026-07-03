"use client";

import { useState } from "react";
import { BookStep } from "./book-step";
import { IntroStep } from "./intro-step";
import { KeyStep } from "./key-step";
import { StepIndicator } from "./step-indicator";

interface BookPickerProps {
  /** "book" = step 1, "key" = step 2, null = closed */
  step: "book" | "key" | null;
  /** True when re-prompting after a backend key rejection */
  keyInvalid?: boolean;
  onConfirmBook: (bookId: string, name: string) => void;
  onSaveKey: (key: string) => void;
  /** Called when the user opts to skip the key step */
  onSkip?: () => void;
}

/**
 * Setup flow modal. Owns the modal shell + shared branding and routes between
 * the intro, notebook, and API-key steps — each of which lives in its own file
 * and manages its own local form state.
 */
export function BookPicker({ step, keyInvalid = false, onConfirmBook, onSaveKey, onSkip }: BookPickerProps) {
  // A welcome/overview screen shown once before notebook selection.
  const [showIntro, setShowIntro] = useState(true);

  if (!step) return null;

  const showIntroCard = step === "book" && showIntro;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <div aria-hidden className="absolute inset-0 bg-black/50 backdrop-blur-sm" />

      <div className="relative z-10 flex w-full max-w-md flex-col rounded-2xl border border-[var(--border)] bg-[var(--surface)] shadow-2xl">

        {!showIntroCard && <StepIndicator step={step} />}

        {/* ── Shared header branding ── */}
        <div className="flex flex-col items-center border-b border-[var(--border)] px-5 py-5 text-center">
          <h2 className="mt-3 text-base font-semibold tracking-tight">Welcome to Atlas</h2>
          <p className="mt-1 text-xs text-[var(--subtle)]">
            Atlas is a curated demo designed to highlight my work with Agentic AI. I invite you to take your time exploring the project and learning about its features.
          </p>
        </div>

        {showIntroCard && <IntroStep onStart={() => setShowIntro(false)} />}

        {step === "book" && !showIntro && <BookStep onConfirm={onConfirmBook} />}

        {step === "key" && <KeyStep keyInvalid={keyInvalid} onSave={onSaveKey} onSkip={onSkip} />}
      </div>
    </div>
  );
}
