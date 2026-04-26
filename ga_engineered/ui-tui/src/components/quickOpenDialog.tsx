import { Text, useInput } from "ink";
import React, { useState } from "react";

import { DialogFrame } from "./dialog.js";
import { FuzzyPicker, type FuzzyPickerItem, clampSelection } from "./fuzzyPicker.js";
import { SearchBox } from "./searchBox.js";

interface QuickOpenDialogProps {
  matches: readonly { path: string }[];
  loading: boolean;
  onQueryChange: (query: string) => void;
  onSelect: (path: string) => void;
  onCancel: () => void;
  maxRows?: number;
}

export function QuickOpenDialog({
  matches,
  loading,
  onQueryChange,
  onSelect,
  onCancel,
  maxRows = 8,
}: QuickOpenDialogProps): React.ReactElement {
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(0);
  const items: FuzzyPickerItem[] = matches.map((match) => ({
    id: match.path,
    label: match.path,
  }));

  const updateQuery = (next: string): void => {
    setQuery(next);
    setSelected(0);
    onQueryChange(next);
  };

  useInput((input, key) => {
    if (key.escape) {
      onCancel();
      return;
    }
    if (key.return || key.tab) {
      const pick = matches[selected] ?? matches[0];
      if (pick) onSelect(pick.path);
      return;
    }
    if (key.upArrow) {
      setSelected((idx) => clampSelection(idx - 1, matches.length));
      return;
    }
    if (key.downArrow) {
      setSelected((idx) => clampSelection(idx + 1, matches.length));
      return;
    }
    if (key.backspace || key.delete) {
      updateQuery(query.slice(0, -1));
      return;
    }
    if (input && !key.ctrl && !key.meta) {
      updateQuery(query + input);
    }
  });

  return (
    <DialogFrame title="quick open" instructions="type path · ↑↓ pick · Enter insert · Esc cancel">
      <SearchBox query={query} placeholder="file path" />
      {loading && matches.length === 0 ? (
        <Text color="gray" dimColor>
          searching…
        </Text>
      ) : (
        <FuzzyPicker items={items} selectedIndex={selected} maxRows={maxRows} />
      )}
    </DialogFrame>
  );
}
