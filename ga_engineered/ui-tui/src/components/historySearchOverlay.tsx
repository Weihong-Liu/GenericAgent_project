/**
 * Ctrl-R history search overlay.
 *
 * Mounts above the input box, takes focus, lets the user type a query
 * and pick a previous entry with arrow keys + Enter. Esc cancels.
 */

import { Text, useInput } from "ink";
import React, { useCallback, useState } from "react";

import type { HistoryEntry, InputMode } from "../hooks/useInputHistory.js";
import { DialogFrame } from "./dialog.js";
import { FuzzyPicker, type FuzzyPickerItem } from "./fuzzyPicker.js";
import { SearchBox } from "./searchBox.js";

export interface HistorySearchProps {
  history: readonly HistoryEntry[];
  mode: InputMode;
  onSelect: (text: string) => void;
  onCancel: () => void;
  /** Optional limit on rendered rows. */
  maxRows?: number;
}

export function HistorySearchOverlay({
  history,
  mode,
  onSelect,
  onCancel,
  maxRows = 8,
}: HistorySearchProps): React.ReactElement {
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(0);
  const matches = scoreMatches(history, mode, query);
  const visible = matches.slice(0, maxRows);
  const pickerItems: FuzzyPickerItem[] = matches.map((entry, idx) => ({
    id: `${entry.text}-${idx}`,
    label: singleLine(entry.text),
  }));

  useInput((input, key) => {
    if (key.escape) {
      onCancel();
      return;
    }
    if (key.return) {
      const pick = visible[selected];
      if (pick) onSelect(pick.text);
      else onCancel();
      return;
    }
    if (key.upArrow) {
      setSelected((idx) => Math.max(0, idx - 1));
      return;
    }
    if (key.downArrow) {
      setSelected((idx) => Math.min(Math.max(0, visible.length - 1), idx + 1));
      return;
    }
    if (key.backspace || key.delete) {
      setQuery((q) => q.slice(0, -1));
      setSelected(0);
      return;
    }
    if (input && !key.ctrl && !key.meta) {
      setQuery((q) => q + input);
      setSelected(0);
    }
  });

  const reset = useCallback(() => {
    setQuery("");
    setSelected(0);
  }, []);
  void reset;

  return (
    <DialogFrame
      title={`search history (${mode})`}
      instructions="↑↓ pick · Enter use · Esc cancel"
    >
      <SearchBox query={query} />
      {visible.length === 0 ? (
        <Text color="gray" dimColor>
          {history.length === 0 ? "no history yet" : "no matches"}
        </Text>
      ) : (
        <FuzzyPicker items={pickerItems} selectedIndex={selected} maxRows={maxRows} />
      )}
    </DialogFrame>
  );
}

function singleLine(text: string): string {
  const oneLine = text.replace(/\s+/g, " ").trim();
  return oneLine.length > 100 ? oneLine.slice(0, 99) + "…" : oneLine;
}

interface Scored {
  text: string;
  score: number;
}

function scoreMatches(
  history: readonly HistoryEntry[],
  mode: InputMode,
  query: string,
): Scored[] {
  const filtered = history.filter((entry) => entry.mode === mode);
  if (query.length === 0) {
    return filtered
      .slice()
      .reverse()
      .map((entry) => ({ text: entry.text, score: 0 }));
  }
  const lower = query.toLowerCase();
  const scored: Scored[] = [];
  for (const entry of filtered) {
    const idx = entry.text.toLowerCase().indexOf(lower);
    if (idx === -1) continue;
    // Lower score = better; -idx so prefix matches sort first.
    scored.push({ text: entry.text, score: -idx });
  }
  scored.sort((a, b) => b.score - a.score);
  // Dedup adjacent identical entries to prevent spammy lists.
  const out: Scored[] = [];
  for (const entry of scored) {
    if (out[out.length - 1]?.text !== entry.text) out.push(entry);
  }
  return out;
}
