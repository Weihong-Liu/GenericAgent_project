import { Box, Text } from "ink";
import React from "react";

import type { InputMode } from "../../state/modeDetector.js";
import type { QueuedPrompt } from "../../state/promptQueue.js";

interface PromptFooterProps {
  mode: InputMode;
  busy: boolean;
  queued: readonly QueuedPrompt[];
  stashedPrompt: string | null;
}

export function PromptFooter({
  mode,
  busy,
  queued,
  stashedPrompt,
}: PromptFooterProps): React.ReactElement | null {
  if (!busy && queued.length === 0 && stashedPrompt === null && mode === "chat") {
    return null;
  }

  const next = queued[0];
  return (
    <Box marginTop={1}>
      <Text color="gray" dimColor>
        mode{" "}
      </Text>
      <Text color={modeColor(mode)} bold>
        {mode}
      </Text>
      {busy ? (
        <Text color="gray" dimColor>
          {" · running"}
        </Text>
      ) : null}
      {queued.length > 0 ? (
        <Text color="yellow">
          {" · queued "}
          {queued.length}
          {next ? <Text color="gray"> next: {singleLine(next.text)}</Text> : null}
        </Text>
      ) : null}
      {stashedPrompt !== null ? (
        <Text color="magenta">
          {" · stash "}
          <Text color="gray">Ctrl-Y restore: {singleLine(stashedPrompt)}</Text>
        </Text>
      ) : null}
    </Box>
  );
}

function modeColor(mode: InputMode): string {
  switch (mode) {
    case "bash":
      return "yellow";
    case "slash":
      return "cyan";
    case "mention":
      return "magenta";
    case "chat":
      return "gray";
  }
}

function singleLine(text: string): string {
  const trimmed = text.replace(/\s+/g, " ").trim();
  return trimmed.length > 50 ? trimmed.slice(0, 49) + "…" : trimmed;
}
