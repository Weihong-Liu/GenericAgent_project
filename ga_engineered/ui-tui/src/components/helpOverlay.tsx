/**
 * Keyboard-shortcut help overlay shown by ``?`` or ``/shortcuts``.
 * Esc / any keystroke closes it.
 */

import { Box, Text, useInput } from "ink";
import React from "react";

import { DialogFrame } from "./dialog.js";

interface HelpOverlayProps {
  onClose: () => void;
}

export function HelpOverlay({ onClose }: HelpOverlayProps): React.ReactElement {
  useInput(() => onClose());

  return (
    <DialogFrame title="keyboard shortcuts" footer="any key to close" border>
      <Box flexDirection="column" marginTop={1}>
        {ROWS.map(([key, desc]) => (
          <Text key={key}>
            <Text color="yellow">{key.padEnd(18)}</Text>
            <Text color="gray">{desc}</Text>
          </Text>
        ))}
      </Box>
    </DialogFrame>
  );
}

const ROWS: ReadonlyArray<readonly [string, string]> = [
  ["Enter", "submit (Shift-Enter inserts newline)"],
  ["↑ / ↓", "history recall on the first/last line"],
  ["Tab", "accept slash command or file mention"],
  ["Ctrl-R", "search history"],
  ["Ctrl-S", "open session browser"],
  ["Ctrl-B", "show background tasks"],
  ["Ctrl-J", "show worktree status"],
  ["Ctrl-W", "delete previous word"],
  ["Ctrl-U / Ctrl-K", "kill to line start / end"],
  ["Ctrl-A / Ctrl-E", "jump to line start / end"],
  ["Shift-↑", "open message navigator"],
  ["Space", "expand selected tool result (in navigator)"],
  ["Ctrl-G", "interrupt running turn"],
  ["Ctrl-L", "clear transcript"],
  ["Ctrl-C", "cancel turn / second press exits"],
  ["Ctrl-D", "exit when input is empty"],
  ["Esc", "close overlays / exit insert mode (vim)"],
  ["? or /shortcuts", "show this help"],
  ["! prefix", "run shell command directly"],
  ["@ prefix", "fuzzy file mention"],
  ["/ prefix", "slash command"],
];
