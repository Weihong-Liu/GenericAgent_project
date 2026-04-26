import { describe, expect, it } from "vitest";

import { filterSessions } from "../components/sessionBrowser.js";
import type { SessionSummary } from "../schemas.js";

const SESSIONS: SessionSummary[] = [
  {
    id: "default",
    title: "Current chat",
    parent_session_id: null,
    provider: "openai",
    model: "gpt-5.4",
    created_at: "",
    updated_at: "",
    message_count: 2,
    current: true,
    persisted: false,
  },
  {
    id: "saved-session",
    title: "Migration notes",
    parent_session_id: null,
    provider: "anthropic",
    model: "claude",
    created_at: "2026-04-26T00:00:00Z",
    updated_at: "2026-04-26T00:01:00Z",
    message_count: 4,
    current: false,
    persisted: true,
  },
];

describe("filterSessions", () => {
  it("keeps all sessions for an empty query", () => {
    expect(filterSessions(SESSIONS, "").map((session) => session.id)).toEqual([
      "default",
      "saved-session",
    ]);
  });

  it("matches title, provider, and model fields", () => {
    expect(filterSessions(SESSIONS, "migration").map((session) => session.id)).toEqual([
      "saved-session",
    ]);
    expect(filterSessions(SESSIONS, "gpt").map((session) => session.id)).toEqual([
      "default",
    ]);
  });
});
