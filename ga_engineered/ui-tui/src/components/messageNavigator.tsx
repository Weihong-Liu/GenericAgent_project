/**
 * Read-only message navigator. Activated by Shift-↑.
 *
 * The navigator does not own any transcript state — the parent passes
 * the items + the currently-selected index. Up/Down move the
 * selection, Space toggles the selected tool's expanded flag (via
 * the parent's ``onToggle``), Esc exits.
 */

import { Box, Text } from "ink";
import React from "react";

import type { TranscriptItem } from "../state/transcriptStore.js";
import { computeMessageWindow } from "./virtualMessageList.js";

export interface NavigatorProps {
  items: readonly TranscriptItem[];
  selectedIndex: number;
  maxRows?: number;
}

export function MessageNavigator({
  items,
  selectedIndex,
  maxRows = 8,
}: NavigatorProps): React.ReactElement {
  if (items.length === 0) {
    return (
      <Box flexDirection="column" marginTop={1}>
        <Text color="cyan">── message navigator ──</Text>
        <Text color="gray" dimColor>
          (transcript empty)
        </Text>
      </Box>
    );
  }
  const window = computeMessageWindow(items.length, maxRows, selectedIndex);
  const visible = items.slice(window.start, window.end);
  return (
    <Box flexDirection="column" marginTop={1}>
      <Text color="cyan">
        ── message navigator ({selectedIndex + 1}/{items.length}) ──{" "}
        <Text color="gray" dimColor>
          ↑↓ pick · Space expand · Esc back
        </Text>
      </Text>
      {window.hiddenBefore > 0 ? (
        <Text color="gray" dimColor>
          … earlier messages hidden
        </Text>
      ) : null}
      {visible.map((item, offset) => {
        const idx = window.start + offset;
        const isActive = idx === selectedIndex;
        return (
          <Text key={item.id} color={isActive ? "cyan" : "white"}>
            {isActive ? "❯ " : "  "}
            {summarise(item)}
          </Text>
        );
      })}
      {window.hiddenAfter > 0 ? (
        <Text color="gray" dimColor>
          … newer messages hidden
        </Text>
      ) : null}
    </Box>
  );
}

function summarise(item: TranscriptItem): string {
  switch (item.kind) {
    case "user":
      return `you: ${oneLine(item.text)}`;
    case "assistant":
      return `agent: ${oneLine(item.text || "(streaming…)")}`;
    case "tool": {
      const tail = item.collapsed
        ? `${item.expanded ? "[expanded]" : "[+]"} `
        : "";
      return `tool ${item.name}: ${tail}${oneLine(item.result_preview)}`;
    }
    case "system":
      return `system: ${oneLine(item.text)}`;
    case "error":
      return `error: ${oneLine(item.text)}`;
  }
}

function oneLine(text: string): string {
  const flat = text.replace(/\s+/g, " ").trim();
  return flat.length > 90 ? flat.slice(0, 89) + "…" : flat;
}
