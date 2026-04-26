/**
 * Floating-style file picker shown while the user is typing an
 * ``@<query>`` mention. The picker fetches matches from the gateway's
 * ``files.search`` RPC, debounced to one query per 80 ms.
 */

import { Text } from "ink";
import React from "react";

import { DialogFrame } from "./dialog.js";
import { FuzzyPicker, type FuzzyPickerItem } from "./fuzzyPicker.js";

interface FileMentionOverlayProps {
  matches: readonly { path: string }[];
  selectedIndex: number;
  query: string;
  loading: boolean;
  maxRows?: number;
}

export function FileMentionOverlay({
  matches,
  selectedIndex,
  query,
  loading,
  maxRows = 6,
}: FileMentionOverlayProps): React.ReactElement | null {
  const visible = matches.slice(0, maxRows);
  const overflow = Math.max(0, matches.length - visible.length);
  const items: FuzzyPickerItem[] = matches.map((match) => ({
    id: match.path,
    label: match.path,
  }));

  return (
    <DialogFrame
      title={`@${query || "<files>"}`}
      accentColor="magenta"
      instructions="↑↓ pick · Tab insert · Esc cancel"
    >
      {loading && visible.length === 0 ? (
        <Text color="gray" dimColor>
          searching…
        </Text>
      ) : (
        <FuzzyPicker
          items={items}
          selectedIndex={selectedIndex}
          accentColor="magenta"
          maxRows={maxRows}
          overflowLabel={() => `  …and ${overflow} more`}
        />
      )}
    </DialogFrame>
  );
}
