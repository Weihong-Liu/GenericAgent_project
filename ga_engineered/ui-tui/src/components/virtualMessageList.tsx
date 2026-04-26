import { Box, Text } from "ink";
import React from "react";

import type { TranscriptItem } from "../state/transcriptStore.js";
import { THEME } from "../theme.js";
import { MessageRow } from "./messageRow.js";
import { ThinkingIndicator } from "./thinkingIndicator.js";

interface VirtualMessageListProps {
  items: readonly TranscriptItem[];
  activeRequestId: number | null;
  turnStartedAt: number | null;
  maxRows: number;
  selectedIndex?: number | null;
  transcriptMode?: boolean;
  showAll?: boolean;
}

export interface MessageWindow {
  start: number;
  end: number;
  hiddenBefore: number;
  hiddenAfter: number;
}

export function VirtualMessageList({
  items,
  activeRequestId,
  turnStartedAt,
  maxRows,
  selectedIndex = null,
  transcriptMode = false,
  showAll = false,
}: VirtualMessageListProps): React.ReactElement {
  const window = computeMessageWindow(items.length, maxRows, selectedIndex, showAll);
  const visible = items.slice(window.start, window.end);
  const showPhantomThinking =
    activeRequestId !== null &&
    turnStartedAt !== null &&
    !items.some(
      (item) =>
        item.kind === "assistant" &&
        item.turn_request_id === activeRequestId,
    );

  return (
    <Box flexDirection="column" minHeight={1} marginTop={1}>
      {window.hiddenBefore > 0 ? (
        <Text color={THEME.subtle} dimColor>
          … {window.hiddenBefore} earlier messages hidden
        </Text>
      ) : null}
      {visible.map((item, offset) => {
        const absoluteIndex = window.start + offset;
        return (
          <MessageRow
            key={item.id}
            item={item}
            selected={selectedIndex === absoluteIndex}
            transcriptMode={transcriptMode}
          />
        );
      })}
      {window.hiddenAfter > 0 ? (
        <Text color={THEME.subtle} dimColor>
          … {window.hiddenAfter} newer messages hidden
        </Text>
      ) : null}
      {showPhantomThinking ? <ThinkingIndicator startedAt={turnStartedAt} /> : null}
    </Box>
  );
}

export function computeMessageWindow(
  total: number,
  maxRows: number,
  selectedIndex: number | null = null,
  showAll = false,
): MessageWindow {
  if (showAll) {
    return { start: 0, end: total, hiddenBefore: 0, hiddenAfter: 0 };
  }
  const size = Math.max(1, Math.min(total, maxRows));
  if (total <= size) {
    return { start: 0, end: total, hiddenBefore: 0, hiddenAfter: 0 };
  }

  const selected =
    selectedIndex === null ? total - 1 : Math.min(Math.max(0, selectedIndex), total - 1);
  let start = selected - Math.floor(size / 2);
  start = Math.max(0, Math.min(start, total - size));
  const end = start + size;
  return {
    start,
    end,
    hiddenBefore: start,
    hiddenAfter: total - end,
  };
}
