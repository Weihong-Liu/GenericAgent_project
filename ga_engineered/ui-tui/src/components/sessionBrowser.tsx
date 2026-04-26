import { Text } from "ink";
import React, { useMemo } from "react";

import { DialogFrame } from "./dialog.js";
import { FuzzyPicker, filterFuzzyItems } from "./fuzzyPicker.js";
import type { SessionSummary } from "../schemas.js";

export interface SessionBrowserProps {
  sessions: readonly SessionSummary[];
  query: string;
  selectedIndex: number;
  loading?: boolean;
}

export function SessionBrowser({
  sessions,
  query,
  selectedIndex,
  loading = false,
}: SessionBrowserProps): React.ReactElement {
  const items = useMemo(
    () =>
      filterFuzzyItems(
        sessions.map((session) => ({
          id: session.id,
          label: session.current ? `* ${session.id}` : `  ${session.id}`,
          hint: session.persisted ? `${session.message_count} msg` : "memory",
          description: session.title || session.model || session.provider,
        })),
        query,
      ).map((result) => result.item),
    [sessions, query],
  );

  return (
    <DialogFrame
      title="Sessions"
      accentColor="cyan"
      instructions="type to filter, enter resumes, esc closes"
      footer={`query: ${query || "(all)"}`}
    >
      {loading ? (
        <Text color="gray" dimColor>
          loading sessions...
        </Text>
      ) : (
        <FuzzyPicker
          items={items}
          selectedIndex={selectedIndex}
          maxRows={10}
          emptyLabel="no sessions"
        />
      )}
    </DialogFrame>
  );
}

export function filterSessions(
  sessions: readonly SessionSummary[],
  query: string,
): SessionSummary[] {
  const scored = filterFuzzyItems(
    sessions.map((session) => ({
      id: session.id,
      label: session.id,
      hint: session.title,
      description: `${session.provider} ${session.model}`,
    })),
    query,
  );
  const byId = new Map(sessions.map((session) => [session.id, session]));
  return scored
    .map((result) => byId.get(result.item.id))
    .filter((session): session is SessionSummary => session !== undefined);
}
