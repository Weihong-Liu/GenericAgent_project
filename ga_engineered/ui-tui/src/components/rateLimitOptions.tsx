import { Text } from "ink";
import React from "react";

import { DialogFrame } from "./dialog.js";
import type { RuntimeStatus } from "../schemas.js";

export interface RateLimitOption {
  label: string;
  detail: string;
}

export function buildRateLimitOptions(status: RuntimeStatus | null): RateLimitOption[] {
  const options: RateLimitOption[] = [
    {
      label: "Compact context",
      detail: "Run /compact to reduce prompt size before retrying.",
    },
    {
      label: "Start clean",
      detail: "Run /new or /clear when the current context is no longer needed.",
    },
    {
      label: "Switch model/provider",
      detail: "Run /model or /providers if another configured backend has quota.",
    },
  ];

  if (status?.tokens_budget !== null && status?.tokens_budget !== undefined) {
    options.unshift({
      label: "Current token budget",
      detail: `${status.tokens_used}/${status.tokens_budget} estimated tokens used.`,
    });
  }

  if (status?.provider.includes("codex")) {
    options.push({
      label: "Refresh auth",
      detail: "Run /login openai-codex if the provider reports auth or quota errors.",
    });
  }

  return options;
}

export function RateLimitOptions({
  status,
}: {
  status: RuntimeStatus | null;
}): React.ReactElement {
  const options = buildRateLimitOptions(status);
  return (
    <DialogFrame title="Rate Limit Options" accentColor="yellow" instructions="Esc closes">
      {options.map((option) => (
        <Text key={option.label}>
          <Text bold>{option.label}</Text>{" "}
          <Text color="gray" dimColor>
            {option.detail}
          </Text>
        </Text>
      ))}
    </DialogFrame>
  );
}
