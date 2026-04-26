import { Box, Text } from "ink";
import React from "react";

import type { RuntimeStatus } from "../schemas.js";

export type StatusNoticeLevel = "info" | "warn" | "error";

export interface StatusNotice {
  id: string;
  level: StatusNoticeLevel;
  message: string;
  action: string;
}

const COLOR: Record<StatusNoticeLevel, string> = {
  info: "cyan",
  warn: "yellow",
  error: "red",
};

export function buildStatusNotices(
  status: RuntimeStatus | null,
  dismissed: ReadonlySet<string> = new Set(),
): StatusNotice[] {
  const notices: StatusNotice[] = [];
  if (status === null) {
    notices.push({
      id: "runtime-loading",
      level: "info",
      message: "Runtime status is loading.",
      action: "The TUI will refresh automatically.",
    });
    return notices.filter((notice) => !dismissed.has(notice.id));
  }

  if (status.turn_count === 0) {
    notices.push({
      id: "first-turn",
      level: "info",
      message: "New session is ready.",
      action: "Type a prompt, /help, !command, or @file.",
    });
  }

  if (status.bridge_running === false) {
    notices.push({
      id: "browser-bridge",
      level: "warn",
      message: "Browser bridge is not connected.",
      action: "Run `gae bridge` or install bridge extras before using web_scan.",
    });
  }

  if (status.tokens_budget !== null && status.tokens_budget > 0) {
    const ratio = status.tokens_used / status.tokens_budget;
    if (ratio >= 0.9) {
      notices.push({
        id: "token-budget-critical",
        level: "error",
        message: "Token budget is nearly exhausted.",
        action: "Use /compact or /clear before the next large request.",
      });
    } else if (ratio >= 0.75) {
      notices.push({
        id: "token-budget-warning",
        level: "warn",
        message: "Token budget is getting high.",
        action: "Use /compact soon if the session keeps growing.",
      });
    }
  }

  if (status.provider.includes("codex") && status.turn_count === 0) {
    notices.push({
      id: "codex-auth",
      level: "info",
      message: "Codex provider selected.",
      action: "Run /login openai-codex if auth is missing.",
    });
  }

  return notices.filter((notice) => !dismissed.has(notice.id));
}

export function StatusNotices({
  notices,
  onDismiss,
}: {
  notices: readonly StatusNotice[];
  onDismiss: (id: string) => void;
}): React.ReactElement | null {
  if (notices.length === 0) return null;
  return (
    <Box flexDirection="column" marginBottom={1}>
      {notices.map((notice) => (
        <Text key={notice.id} color={COLOR[notice.level]}>
          {notice.message}{" "}
          <Text color="gray" dimColor>
            {notice.action} · Ctrl-N dismiss
          </Text>
        </Text>
      ))}
    </Box>
  );
}
