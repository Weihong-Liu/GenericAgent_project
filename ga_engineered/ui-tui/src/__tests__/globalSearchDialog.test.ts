import { describe, expect, it } from "vitest";

import { searchTranscript } from "../components/globalSearchDialog.js";
import type { TranscriptItem } from "../state/transcriptStore.js";

const ITEMS: TranscriptItem[] = [
  { id: "u1", kind: "user", text: "open the dashboard" },
  {
    id: "t1",
    kind: "tool",
    tool_use_id: "tool-1",
    name: "web_scan",
    args_preview: "{}",
    result_preview: "Dashboard content",
    result_full: "Dashboard content",
    status: "ok",
    collapsed: false,
    expanded: false,
    started_at: 1,
    finished_at: 2,
    turn_request_id: 1,
  },
  {
    id: "a1",
    kind: "assistant",
    text: "I found the chart",
    streaming: false,
    turn_request_id: 1,
    started_at: 1,
    first_token_at: 1,
  },
];

describe("searchTranscript", () => {
  it("finds matches across user, assistant, and tool rows", () => {
    expect(searchTranscript(ITEMS, "dashboard").map((hit) => hit.index)).toEqual([0, 1]);
    expect(searchTranscript(ITEMS, "chart").map((hit) => hit.index)).toEqual([2]);
  });

  it("returns no results for an empty query", () => {
    expect(searchTranscript(ITEMS, "   ")).toEqual([]);
  });
});
