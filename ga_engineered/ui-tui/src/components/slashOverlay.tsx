/**
 * Floating-style command suggestion list shown when the user types a
 * slash-prefixed draft. Pure presentational; navigation state and Tab
 * handling live in App.tsx so a single ``useInput`` block can manage
 * focus and completion.
 */

import React from "react";

import type { CommandDef } from "../schemas.js";
import { DialogFrame } from "./dialog.js";
import { FuzzyPicker, type FuzzyPickerItem } from "./fuzzyPicker.js";

interface SlashOverlayProps {
  matches: readonly CommandDef[];
  selectedIndex: number;
  /** Cap on how many rows we draw; the rest are summarised. */
  maxRows?: number;
}

export function SlashOverlay({
  matches,
  selectedIndex,
  maxRows = 6,
}: SlashOverlayProps): React.ReactElement | null {
  if (matches.length === 0) return null;

  const overflow = Math.max(0, matches.length - maxRows);
  const items: FuzzyPickerItem[] = matches.map((command) => ({
    id: command.name,
    label: `/${command.name}`,
    ...(command.args_hint ? { hint: command.args_hint } : {}),
    description:
      command.category === "Feature-gated"
        ? `unavailable · ${command.description}`
        : `${command.category} · ${command.description}`,
  }));

  return (
    <DialogFrame title="commands" instructions="↑↓ navigate · Tab complete · Enter run">
      <FuzzyPicker
        items={items}
        selectedIndex={selectedIndex}
        maxRows={maxRows}
        overflowLabel={() => `  …and ${overflow} more (keep typing to narrow)`}
      />
    </DialogFrame>
  );
}
