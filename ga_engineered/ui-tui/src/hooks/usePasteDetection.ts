/**
 * Bracketed-paste detection.
 *
 * Most modern terminals wrap pasted content in ``\x1b[200~`` …
 * ``\x1b[201~`` markers when bracketed-paste mode is enabled. Ink
 * normalises the markers away in some versions, but the *side effect* —
 * a flood of keystrokes arriving in a single tick with newlines
 * embedded — is reliable. We treat any chunk that contains a literal
 * newline OR is longer than 16 chars as a paste, and let the caller
 * suppress submission while the burst lasts.
 */

import { useCallback, useRef } from "react";

const PASTE_BURST_MS = 80;

export interface UsePasteDetectionApi {
  /** True if the most recent input chunk looked like a paste. */
  isPasting: () => boolean;
  /** Feed an input chunk; returns the chunk so callers can chain. */
  observe: (chunk: string) => string;
  /** Manually mark the paste as ended (e.g. on a single key tick). */
  reset: () => void;
}

export function usePasteDetection(): UsePasteDetectionApi {
  const lastObservedAt = useRef<number>(0);
  const isPastingRef = useRef<boolean>(false);

  const observe = useCallback((chunk: string): string => {
    const now = Date.now();
    const looksLikePaste = chunk.length > 16 || chunk.includes("\n");
    if (looksLikePaste) {
      isPastingRef.current = true;
      lastObservedAt.current = now;
    } else if (now - lastObservedAt.current > PASTE_BURST_MS) {
      isPastingRef.current = false;
    }
    return chunk;
  }, []);

  const isPasting = useCallback((): boolean => {
    if (Date.now() - lastObservedAt.current > PASTE_BURST_MS) {
      isPastingRef.current = false;
    }
    return isPastingRef.current;
  }, []);

  const reset = useCallback(() => {
    isPastingRef.current = false;
    lastObservedAt.current = 0;
  }, []);

  return { isPasting, observe, reset };
}
