"use client";

import { useEffect } from "react";

interface TriageKeyboardOptions {
  onNext: () => void;
  onPrev: () => void;
  onConfirm: () => void;
  onOverride: () => void;
  onSkip: () => void;
  onExit: () => void;
  enabled: boolean;
}

export function useTriageKeyboard({
  onNext,
  onPrev,
  onConfirm,
  onOverride,
  onSkip,
  onExit,
  enabled,
}: TriageKeyboardOptions) {
  useEffect(() => {
    if (!enabled) return;

    function handler(e: KeyboardEvent) {
      // Don't intercept when typing in inputs
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;

      switch (e.key) {
        case "ArrowDown":
        case "j":
          e.preventDefault();
          onNext();
          break;
        case "ArrowUp":
        case "k":
          e.preventDefault();
          onPrev();
          break;
        case "Enter":
          e.preventDefault();
          onConfirm();
          break;
        case "o":
        case "O":
          e.preventDefault();
          onOverride();
          break;
        case "s":
        case "S":
          e.preventDefault();
          onSkip();
          break;
        case "Escape":
          e.preventDefault();
          onExit();
          break;
      }
    }

    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [enabled, onNext, onPrev, onConfirm, onOverride, onSkip, onExit]);
}
