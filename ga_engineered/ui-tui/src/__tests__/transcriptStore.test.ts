import { describe, expect, it } from "vitest";

import {
  TranscriptState,
  initialTranscriptState,
  transcriptReducer,
} from "../state/transcriptStore.js";

function feed(state: TranscriptState, ...actions: Parameters<typeof transcriptReducer>[1][]) {
  return actions.reduce((s, a) => transcriptReducer(s, a), state);
}

describe("transcriptReducer", () => {
  it("appends a user item on user_input", () => {
    const next = transcriptReducer(initialTranscriptState, {
      type: "user_input",
      text: "hello",
    });
    expect(next.items).toHaveLength(1);
    expect(next.items[0]).toMatchObject({ kind: "user", text: "hello" });
  });

  it("sets activeTurn but does NOT pre-create an assistant bubble on begin_turn", () => {
    // The bubble is lazy-created on the first content_delta so that a
    // tool_call arriving first lands above the assistant text in the
    // transcript order.
    const next = transcriptReducer(initialTranscriptState, {
      type: "begin_turn",
      request_id: 42,
    });
    expect(next.activeTurn).toBe(42);
    expect(next.items).toHaveLength(0);
  });

  it("late content_delta after end_turn is dropped, not appended", () => {
    const after = feed(
      initialTranscriptState,
      { type: "begin_turn", request_id: 1 },
      {
        type: "event",
        frame: {
          type: "event",
          kind: "content_delta",
          payload: { kind: "content_delta", delta: "live " },
          request_id: 1,
        },
      },
      { type: "end_turn", request_id: 1, final_text: "live" },
      // late delta that races past end_turn — should NOT corrupt the bubble
      {
        type: "event",
        frame: {
          type: "event",
          kind: "content_delta",
          payload: { kind: "content_delta", delta: "STALE" },
          request_id: 1,
        },
      },
    );
    const assistant = after.items.find((i) => i.kind === "assistant");
    if (assistant?.kind !== "assistant") throw new Error();
    expect(assistant.text).toBe("live ");
    expect(assistant.streaming).toBe(false);
  });

  it("loop_stopped marks any running tool as cancelled", () => {
    const after = feed(
      initialTranscriptState,
      { type: "begin_turn", request_id: 1 },
      {
        type: "event",
        frame: {
          type: "event",
          kind: "tool_call",
          payload: {
            kind: "tool_call",
            tool_call: { id: "t1", name: "shell", arguments: {} },
          },
          request_id: 1,
        },
      },
      // No tool_result before the loop_stopped — simulates an
      // interrupted run.
      {
        type: "event",
        frame: {
          type: "event",
          kind: "loop_stopped",
          payload: { kind: "loop_stopped", reason: "stop_signal" },
        },
      },
    );
    const tool = after.items.find((i) => i.kind === "tool");
    if (tool?.kind !== "tool") throw new Error();
    expect(tool.status).toBe("error");
    expect(tool.result_full).toContain("cancelled");
    expect(tool.finished_at).not.toBeNull();
  });

  it("end_turn for a tool-first lazy bubble synthesises the final assistant", () => {
    // Model emits tool_use only; no content_delta. end_turn carries the
    // final assistant text from message_done.
    const after = feed(
      initialTranscriptState,
      { type: "begin_turn", request_id: 5 },
      {
        type: "event",
        frame: {
          type: "event",
          kind: "tool_call",
          payload: {
            kind: "tool_call",
            tool_call: { id: "t1", name: "shell", arguments: { command: "pwd" } },
          },
          request_id: 5,
        },
      },
      { type: "end_turn", request_id: 5, final_text: "Final answer." },
    );
    expect(after.items.map((i) => i.kind)).toEqual(["tool", "assistant"]);
    const assistant = after.items.find((i) => i.kind === "assistant");
    if (assistant?.kind !== "assistant") throw new Error();
    expect(assistant.text).toBe("Final answer.");
    expect(assistant.streaming).toBe(false);
  });

  it("opens a fresh bubble after a tool, keeping text-tool-text-tool order", () => {
    // Regression: previously the second content_delta after a tool
    // would walk back past the tool and merge into the original
    // bubble, leaving every tool stacked at the bottom of the turn.
    const after = feed(
      initialTranscriptState,
      { type: "begin_turn", request_id: 1 },
      {
        type: "event",
        frame: {
          type: "event",
          kind: "content_delta",
          payload: { kind: "content_delta", delta: "first " },
          request_id: 1,
        },
      },
      {
        type: "event",
        frame: {
          type: "event",
          kind: "tool_call",
          payload: {
            kind: "tool_call",
            tool_call: { id: "t1", name: "shell", arguments: {} },
          },
          request_id: 1,
        },
      },
      {
        type: "event",
        frame: {
          type: "event",
          kind: "tool_result",
          payload: {
            kind: "tool_result",
            tool_result: { tool_use_id: "t1", content: "out", is_error: false },
          },
          request_id: 1,
        },
      },
      {
        type: "event",
        frame: {
          type: "event",
          kind: "content_delta",
          payload: { kind: "content_delta", delta: "second" },
          request_id: 1,
        },
      },
      {
        type: "event",
        frame: {
          type: "event",
          kind: "tool_call",
          payload: {
            kind: "tool_call",
            tool_call: { id: "t2", name: "shell", arguments: {} },
          },
          request_id: 1,
        },
      },
    );
    expect(after.items.map((i) => i.kind)).toEqual([
      "assistant",
      "tool",
      "assistant",
      "tool",
    ]);
    const assistants = after.items.filter((i) => i.kind === "assistant");
    if (assistants[0]?.kind !== "assistant" || assistants[1]?.kind !== "assistant") {
      throw new Error("expected two assistant bubbles");
    }
    expect(assistants[0].text).toBe("first ");
    expect(assistants[1].text).toBe("second");
  });

  it("places tool_call above the assistant bubble when emitted first", () => {
    const after = feed(
      initialTranscriptState,
      { type: "begin_turn", request_id: 1 },
      {
        type: "event",
        frame: {
          type: "event",
          kind: "tool_call",
          payload: {
            kind: "tool_call",
            tool_call: { id: "t1", name: "shell", arguments: { command: "ls" } },
          },
          request_id: 1,
        },
      },
      {
        type: "event",
        frame: {
          type: "event",
          kind: "content_delta",
          payload: { kind: "content_delta", delta: "Here you go" },
          request_id: 1,
        },
      },
    );
    const kinds = after.items.map((i) => i.kind);
    expect(kinds).toEqual(["tool", "assistant"]);
  });

  it("appends content_delta into the active assistant bubble", () => {
    const after = feed(
      initialTranscriptState,
      { type: "begin_turn", request_id: 1 },
      {
        type: "event",
        frame: {
          type: "event",
          kind: "content_delta",
          payload: { kind: "content_delta", delta: "He" },
          request_id: 1,
        },
      },
      {
        type: "event",
        frame: {
          type: "event",
          kind: "content_delta",
          payload: { kind: "content_delta", delta: "llo" },
          request_id: 1,
        },
      },
    );

    const assistant = after.items.find((i) => i.kind === "assistant");
    expect(assistant).toBeDefined();
    if (assistant?.kind !== "assistant") throw new Error();
    expect(assistant.text).toBe("Hello");
    expect(assistant.streaming).toBe(true);
  });

  it("opens and closes a tool node from tool_call + tool_result", () => {
    const after = feed(
      initialTranscriptState,
      { type: "begin_turn", request_id: 7 },
      {
        type: "event",
        frame: {
          type: "event",
          kind: "tool_call",
          payload: {
            kind: "tool_call",
            tool_call: { id: "t1", name: "shell", arguments: { cmd: "ls" } },
          },
          request_id: 7,
        },
      },
      {
        type: "event",
        frame: {
          type: "event",
          kind: "tool_result",
          payload: {
            kind: "tool_result",
            tool_result: { tool_use_id: "t1", content: "out", is_error: false },
          },
          request_id: 7,
        },
      },
    );

    const tool = after.items.find((i) => i.kind === "tool");
    expect(tool).toBeDefined();
    if (tool?.kind !== "tool") throw new Error();
    expect(tool.name).toBe("shell");
    expect(tool.status).toBe("ok");
    expect(tool.result_preview).toBe("out");
    expect(tool.finished_at).not.toBeNull();
  });

  it("marks tool node as error on is_error=true", () => {
    const after = feed(
      initialTranscriptState,
      { type: "begin_turn", request_id: 1 },
      {
        type: "event",
        frame: {
          type: "event",
          kind: "tool_call",
          payload: {
            kind: "tool_call",
            tool_call: { id: "t1", name: "shell", arguments: {} },
          },
          request_id: 1,
        },
      },
      {
        type: "event",
        frame: {
          type: "event",
          kind: "tool_result",
          payload: {
            kind: "tool_result",
            tool_result: { tool_use_id: "t1", content: "boom", is_error: true },
          },
          request_id: 1,
        },
      },
    );
    const tool = after.items.find((i) => i.kind === "tool");
    if (tool?.kind !== "tool") throw new Error();
    expect(tool.status).toBe("error");
  });

  it("end_turn clears streaming and resets activeTurn", () => {
    const after = feed(
      initialTranscriptState,
      { type: "begin_turn", request_id: 5 },
      { type: "end_turn", request_id: 5, final_text: "done" },
    );
    expect(after.activeTurn).toBeNull();
    const assistant = after.items.find((i) => i.kind === "assistant");
    if (assistant?.kind !== "assistant") throw new Error();
    expect(assistant.streaming).toBe(false);
  });

  it("end_turn falls back to final_text when no deltas arrived", () => {
    const after = feed(
      initialTranscriptState,
      { type: "begin_turn", request_id: 9 },
      { type: "end_turn", request_id: 9, final_text: "fallback" },
    );
    const assistant = after.items.find((i) => i.kind === "assistant");
    if (assistant?.kind !== "assistant") throw new Error();
    expect(assistant.text).toBe("fallback");
  });

  it("late content_delta after end_turn does not spawn a phantom bubble", () => {
    const after = feed(
      initialTranscriptState,
      { type: "begin_turn", request_id: 1 },
      { type: "end_turn", request_id: 1, final_text: "ok" },
      {
        type: "event",
        frame: {
          type: "event",
          kind: "content_delta",
          payload: { kind: "content_delta", delta: "stale" },
          request_id: 1,
        },
      },
    );
    const assistants = after.items.filter((i) => i.kind === "assistant");
    // Exactly one assistant bubble; the stale delta is appended to it but no
    // new streaming bubble is created.
    expect(assistants).toHaveLength(1);
  });

  it("collapses tool result when content exceeds threshold", () => {
    const longText = "x".repeat(500);
    const after = feed(
      initialTranscriptState,
      { type: "begin_turn", request_id: 1 },
      {
        type: "event",
        frame: {
          type: "event",
          kind: "tool_call",
          payload: {
            kind: "tool_call",
            tool_call: { id: "t1", name: "shell", arguments: {} },
          },
          request_id: 1,
        },
      },
      {
        type: "event",
        frame: {
          type: "event",
          kind: "tool_result",
          payload: {
            kind: "tool_result",
            tool_result: { tool_use_id: "t1", content: longText, is_error: false },
          },
          request_id: 1,
        },
      },
    );
    const tool = after.items.find((i) => i.kind === "tool");
    if (tool?.kind !== "tool") throw new Error();
    expect(tool.collapsed).toBe(true);
    expect(tool.expanded).toBe(false);
    expect(tool.result_full).toBe(longText);
    expect(tool.result_preview.length).toBeLessThan(longText.length);
  });

  it("toggle_tool flips the expanded flag for the matching tool", () => {
    const after = feed(
      initialTranscriptState,
      { type: "begin_turn", request_id: 1 },
      {
        type: "event",
        frame: {
          type: "event",
          kind: "tool_call",
          payload: {
            kind: "tool_call",
            tool_call: { id: "t1", name: "shell", arguments: {} },
          },
          request_id: 1,
        },
      },
      {
        type: "event",
        frame: {
          type: "event",
          kind: "tool_result",
          payload: {
            kind: "tool_result",
            tool_result: { tool_use_id: "t1", content: "y".repeat(400), is_error: false },
          },
          request_id: 1,
        },
      },
      { type: "toggle_tool", tool_use_id: "t1" },
    );
    const tool = after.items.find((i) => i.kind === "tool");
    if (tool?.kind !== "tool") throw new Error();
    expect(tool.expanded).toBe(true);
  });

  it("malformed tool_call payload surfaces an error item", () => {
    const after = transcriptReducer(initialTranscriptState, {
      type: "event",
      frame: {
        type: "event",
        kind: "tool_call",
        payload: { kind: "tool_call", tool_call: { name: "shell" } }, // missing id, arguments
        request_id: 1,
      },
    });
    const errors = after.items.filter((i) => i.kind === "error");
    expect(errors).toHaveLength(1);
    if (errors[0]?.kind === "error") {
      expect(errors[0].text).toContain("malformed tool_call");
    }
  });

  it("error events append a red error item", () => {
    const after = transcriptReducer(initialTranscriptState, {
      type: "event",
      frame: {
        type: "event",
        kind: "error",
        payload: { kind: "error", error: "kaboom" },
      },
    });
    const item = after.items.find((i) => i.kind === "error");
    expect(item?.kind).toBe("error");
    if (item?.kind === "error") expect(item.text).toBe("kaboom");
  });
});
