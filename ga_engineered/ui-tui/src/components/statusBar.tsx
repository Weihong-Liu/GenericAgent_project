/**
 * Bottom status bar.
 *
 * Renders ``provider · model · turn N/max · tokens M/budget · busy/idle ·
 * /help /commands /exit`` in a single dim line. When tokens are within
 * 90 % of the configured budget, the tokens segment switches to red.
 */

import { Box, Text } from "ink";
import React from "react";

import type { RuntimeStatus } from "../schemas.js";
import { THEME } from "../theme.js";

interface StatusBarProps {
  status: RuntimeStatus | null;
  busy: boolean;
  vimMode?: "insert" | "normal" | "visual" | "operator" | null;
  transcriptMode?: boolean;
  showAll?: boolean;
  width?: number;
}

export function StatusBar({
  status,
  busy,
  vimMode,
  transcriptMode = false,
  showAll = false,
  width = 80,
}: StatusBarProps): React.ReactElement {
  if (status === null) {
    return (
      <Box marginTop={1}>
        <Text color={THEME.subtle} dimColor>
          loading status…
        </Text>
      </Box>
    );
  }

  // Free-code style: single dim line, ``·``-separated. No emoji, no
  // multi-colour traffic lights — just the model + turn + tokens + a
  // mode pill when needed.
  const turnAtLimit = status.turn_count >= status.max_turns;
  const tokenColor = tokenSegmentColor(status.tokens_used, status.tokens_budget);
  return (
    <Box flexDirection="column" marginTop={1}>
      {transcriptMode ? (
        <>
          <Text color={THEME.subtle} dimColor>
            {"─".repeat(Math.max(8, width))}
          </Text>
          <Text color={THEME.subtle} dimColor>
            {"  Showing detailed transcript · ctrl+o to toggle · ctrl+e to show all"}
            {"        "}
            {showAll ? "all" : "verbose"}
          </Text>
        </>
      ) : null}
      <Box>
        <Text color={THEME.subtle} dimColor>
          {status.model}
        </Text>
        <Text color={THEME.subtle} dimColor>
          {" · "}
        </Text>
        <Text color={turnAtLimit ? THEME.error : THEME.subtle} dimColor={!turnAtLimit}>
          {status.turn_count}/{status.max_turns} turns
        </Text>
        <Text color={THEME.subtle} dimColor>
          {" · "}
        </Text>
        <Text color={tokenColor} dimColor={tokenColor === THEME.subtle}>
          {formatTokens(status.tokens_used)} tokens
        </Text>
        <Text color={THEME.subtle} dimColor>
          {" · "}
          {busy ? "running" : "ready"}
        </Text>
        {vimMode ? (
          <Text color={vimMode === "insert" ? THEME.startupAccent : THEME.suggestion} bold>
            {" "}
            {vimMode.toUpperCase()}
          </Text>
        ) : null}
      </Box>
    </Box>
  );
}

function tokenSegmentColor(used: number, budget: number | null): string {
  if (budget === null || budget <= 0) return THEME.subtle;
  const ratio = used / budget;
  if (ratio >= 0.9) return THEME.error;
  if (ratio >= 0.75) return THEME.warning;
  return THEME.subtle;
}

function formatTokens(n: number): string {
  if (n < 1000) return String(n);
  if (n < 10_000) return `${(n / 1000).toFixed(1)}k`;
  return `${Math.round(n / 1000)}k`;
}
