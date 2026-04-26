import { Text, useInput } from "ink";
import React, { useMemo, useState } from "react";

import type { TranscriptItem } from "../state/transcriptStore.js";
import { DialogFrame } from "./dialog.js";
import { FuzzyPicker, type FuzzyPickerItem, clampSelection } from "./fuzzyPicker.js";
import { SearchBox } from "./searchBox.js";

interface GlobalSearchDialogProps {
  items: readonly TranscriptItem[];
  onSelect: (index: number) => void;
  onCancel: () => void;
  maxRows?: number;
}

interface SearchHit extends FuzzyPickerItem {
  index: number;
}

export function GlobalSearchDialog({
  items,
  onSelect,
  onCancel,
  maxRows = 8,
}: GlobalSearchDialogProps): React.ReactElement {
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(0);
  const hits = useMemo(() => searchTranscript(items, query), [items, query]);

  useInput((input, key) => {
    if (key.escape) {
      onCancel();
      return;
    }
    if (key.return) {
      const pick = hits[selected] ?? hits[0];
      if (pick) onSelect(pick.index);
      return;
    }
    if (key.upArrow) {
      setSelected((idx) => clampSelection(idx - 1, hits.length));
      return;
    }
    if (key.downArrow) {
      setSelected((idx) => clampSelection(idx + 1, hits.length));
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

  return (
    <DialogFrame title="global search" instructions="search transcript · Enter jump · Esc cancel">
      <SearchBox query={query} placeholder="search transcript" />
      {query.trim() && hits.length === 0 ? (
        <Text color="gray" dimColor>
          no matches
        </Text>
      ) : (
        <FuzzyPicker items={hits} selectedIndex={selected} maxRows={maxRows} />
      )}
    </DialogFrame>
  );
}

export function searchTranscript(
  items: readonly TranscriptItem[],
  query: string,
): SearchHit[] {
  const needle = query.trim().toLowerCase();
  if (!needle) return [];
  const hits: SearchHit[] = [];
  for (const [index, item] of items.entries()) {
    const text = transcriptText(item);
    const at = text.toLowerCase().indexOf(needle);
    if (at === -1) continue;
    hits.push({
      id: item.id,
      index,
      label: `${item.kind}: ${singleLine(text)}`,
      description: `match at ${at + 1}`,
    });
  }
  return hits;
}

function transcriptText(item: TranscriptItem): string {
  switch (item.kind) {
    case "user":
    case "assistant":
    case "system":
    case "error":
      return item.text;
    case "tool":
      return `${item.name} ${item.args_preview} ${item.result_preview} ${item.result_full}`;
  }
}

function singleLine(text: string): string {
  const flat = text.replace(/\s+/g, " ").trim();
  return flat.length > 70 ? flat.slice(0, 69) + "…" : flat;
}
