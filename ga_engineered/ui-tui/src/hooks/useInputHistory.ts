/**
 * Up/Down arrow history recall, with mode-filtered chunks and a
 * draft slot that gets restored when the user steps past the bottom.
 *
 * The hook is purely client-side; it does NOT persist. Persistence is
 * a separate adapter (see ``loadHistory`` / ``appendHistory`` in
 * ``../persistence/historyFile.ts``).
 */

import { useCallback, useRef, useState } from "react";

export type InputMode = "chat" | "bash";

export interface HistoryEntry {
  mode: InputMode;
  text: string;
}

export interface UseInputHistoryArgs {
  initial?: HistoryEntry[];
  /**
   * Called whenever the hook commits a new entry (e.g. after submit).
   * Implementations append to the persistent file.
   */
  onCommit?: (entry: HistoryEntry) => void;
}

export interface UseInputHistoryApi {
  /** Recall the previous entry of the current mode. */
  prev: (mode: InputMode, currentDraft: string) => string | null;
  /** Recall the next entry, or restore the draft when we walk off the end. */
  next: (mode: InputMode, currentDraft: string) => string | null;
  /** Remember a fresh entry once the user submits. */
  commit: (entry: HistoryEntry) => void;
  /** Drop any in-flight recall state — call this after a submit. */
  reset: () => void;
  /** Current cursor index into the filtered history (for tests / debug). */
  index: () => number;
}

export function useInputHistory({
  initial = [],
  onCommit,
}: UseInputHistoryArgs = {}): UseInputHistoryApi {
  const [entries, setEntries] = useState<HistoryEntry[]>(initial);
  const indexRef = useRef<number>(-1);
  const draftRef = useRef<string>("");

  const filteredFor = useCallback(
    (mode: InputMode) => entries.filter((entry) => entry.mode === mode),
    [entries],
  );

  const prev = useCallback(
    (mode: InputMode, currentDraft: string): string | null => {
      const list = filteredFor(mode);
      if (list.length === 0) return null;

      // Stash the draft on the first up-press so we can restore it on
      // the way back down.
      if (indexRef.current === -1) draftRef.current = currentDraft;

      const next = indexRef.current === -1 ? list.length - 1 : Math.max(0, indexRef.current - 1);
      indexRef.current = next;
      return list[next]?.text ?? null;
    },
    [filteredFor],
  );

  const next = useCallback(
    (mode: InputMode, _currentDraft: string): string | null => {
      const list = filteredFor(mode);
      if (list.length === 0 || indexRef.current === -1) return null;

      if (indexRef.current >= list.length - 1) {
        // Walked past the newest entry — restore the original draft.
        indexRef.current = -1;
        const draft = draftRef.current;
        draftRef.current = "";
        return draft;
      }
      indexRef.current += 1;
      return list[indexRef.current]?.text ?? null;
    },
    [filteredFor],
  );

  const commit = useCallback(
    (entry: HistoryEntry) => {
      // Skip empty / duplicate-of-previous entries — matches free-code's
      // shell-style dedup.
      if (entry.text.trim().length === 0) return;
      const last = entries[entries.length - 1];
      if (last && last.mode === entry.mode && last.text === entry.text) return;
      setEntries((prevEntries) => [...prevEntries, entry]);
      onCommit?.(entry);
    },
    [entries, onCommit],
  );

  const reset = useCallback(() => {
    indexRef.current = -1;
    draftRef.current = "";
  }, []);

  const index = useCallback(() => indexRef.current, []);

  return { prev, next, commit, reset, index };
}
