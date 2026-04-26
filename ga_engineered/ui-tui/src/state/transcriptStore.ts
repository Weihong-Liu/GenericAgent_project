/**
 * Reducer-based transcript state.
 *
 * The store is intentionally framework-agnostic — App.tsx wires it into a
 * useReducer call. Keeping it here makes it trivial to unit-test the
 * event-to-UI translation in isolation, without rendering Ink.
 */

import type { EventFrame } from "../schemas.js";
import { toolCallPayloadSchema, toolResultPayloadSchema } from "../schemas.js";

export type TranscriptItemKind =
  | "user"
  | "assistant"
  | "tool"
  | "system"
  | "error";

export interface UserItem {
  id: string;
  kind: "user";
  text: string;
}

export interface AssistantItem {
  id: string;
  kind: "assistant";
  text: string;
  /** True while the turn is still streaming. */
  streaming: boolean;
  turn_request_id: number;
  /** Wall-clock ms when ``begin_turn`` fired (used for "thought for"). */
  started_at: number;
  /** Wall-clock ms when the first content_delta arrived; null until then. */
  first_token_at: number | null;
  /** Wall-clock ms when ``end_turn`` finalized this assistant bubble. */
  finished_at?: number | null;
}

export type ToolStatus = "running" | "ok" | "error";

export interface ToolItem {
  id: string;
  kind: "tool";
  tool_use_id: string;
  name: string;
  args_preview: string;
  status: ToolStatus;
  result_preview: string;
  /** Full result text (kept so a user can expand long output later). */
  result_full: string;
  /** True when ``result_full`` exceeds the preview threshold. */
  collapsed: boolean;
  /** Whether the user has explicitly expanded this row. */
  expanded: boolean;
  started_at: number;
  finished_at: number | null;
  turn_request_id: number;
}

export interface SystemItem {
  id: string;
  kind: "system";
  text: string;
}

export interface ErrorItem {
  id: string;
  kind: "error";
  text: string;
}

export type TranscriptItem =
  | UserItem
  | AssistantItem
  | ToolItem
  | SystemItem
  | ErrorItem;

export interface TranscriptState {
  items: TranscriptItem[];
  /** request_id of the chat.send currently being streamed, if any. */
  activeTurn: number | null;
  /**
   * Wall-clock ms when each turn began, keyed by request_id. The
   * lazy-created assistant bubble reads from here so its
   * ``started_at`` reflects the actual ``begin_turn`` time, not the
   * time of the first content_delta (which would zero out
   * ``thought for Ns``).
   */
  turnStartedAt: Record<number, number>;
}

export type TranscriptAction =
  | { type: "user_input"; text: string }
  | { type: "system"; text: string }
  | { type: "begin_turn"; request_id: number }
  | { type: "event"; frame: EventFrame }
  | { type: "end_turn"; request_id: number; final_text: string }
  | { type: "command_output"; content: string; is_error: boolean }
  | { type: "toggle_tool"; tool_use_id: string };

/**
 * Tool results are collapsed by default (matching free-code) so the
 * transcript stays scannable. The user expands either with Space (in
 * the message navigator) or Ctrl-O (most recent collapsed result).
 * Errors are NEVER collapsed — the user always needs the message.
 */
const COLLAPSE_THRESHOLD = 0;

let counter = 0;
const nextId = (): string => `i${++counter}`;

export const initialTranscriptState: TranscriptState = {
  items: [],
  activeTurn: null,
  turnStartedAt: {},
};

export function transcriptReducer(
  state: TranscriptState,
  action: TranscriptAction,
): TranscriptState {
  switch (action.type) {
    case "user_input":
      return appendItem(state, {
        id: nextId(),
        kind: "user",
        text: action.text,
      });

    case "system":
      return appendItem(state, { id: nextId(), kind: "system", text: action.text });

    case "begin_turn":
      // Do NOT pre-create an empty assistant bubble — that would force
      // the assistant row to appear above any later tool_call event for
      // the same turn, even when the model actually emitted the
      // tool_use FIRST. The bubble is lazy-created on the first
      // content_delta. We record the real begin_turn timestamp here
      // so the lazy bubble can use it as ``started_at`` (otherwise
      // the "thought for Ns" badge would always read 0s).
      return {
        ...state,
        activeTurn: action.request_id,
        turnStartedAt: { ...state.turnStartedAt, [action.request_id]: Date.now() },
      };

    case "event":
      return reduceEvent(state, action.frame);

    case "end_turn":
      return finalizeTurn(state, action.request_id, action.final_text);

    case "command_output":
      return appendItem(state, {
        id: nextId(),
        kind: action.is_error ? "error" : "system",
        text: action.content,
      });

    case "toggle_tool": {
      const items = state.items.map((item): TranscriptItem => {
        if (item.kind === "tool" && item.tool_use_id === action.tool_use_id) {
          return { ...item, expanded: !item.expanded };
        }
        return item;
      });
      return { ...state, items };
    }

    default:
      return state;
  }
}

function appendItem(state: TranscriptState, item: TranscriptItem): TranscriptState {
  return { ...state, items: [...state.items, item] };
}

function reduceEvent(state: TranscriptState, frame: EventFrame): TranscriptState {
  const turnId = frame.request_id ?? null;

  switch (frame.kind) {
    case "content_delta":
      return appendDelta(state, turnId, asString(frame.payload.delta));

    case "tool_call":
      return openToolCall(state, frame, turnId);

    case "tool_result":
      return closeToolCall(state, frame, turnId);

    case "error":
      return appendItem(state, {
        id: nextId(),
        kind: "error",
        text: asString(frame.payload.error),
      });

    case "loop_stopped": {
      // Mark any tool still in ``running`` state as cancelled so the
      // user doesn't see a perpetual spinner after the loop bailed.
      const reason = asString(frame.payload.reason);
      const items = state.items.map((item): TranscriptItem => {
        if (item.kind === "tool" && item.status === "running") {
          return {
            ...item,
            status: "error",
            result_full: `cancelled: ${reason}`,
            result_preview: `cancelled: ${reason}`,
            collapsed: false,
            finished_at: Date.now(),
          };
        }
        return item;
      });
      return appendItem(
        { ...state, items },
        {
          id: nextId(),
          kind: "system",
          text: `loop stopped: ${reason}`,
        },
      );
    }

    default:
      return state;
  }
}

function appendDelta(
  state: TranscriptState,
  turnId: number | null,
  delta: string,
): TranscriptState {
  if (delta.length === 0) return state;
  const items = [...state.items];
  // Walk backwards looking at the *most recent* item belonging to this
  // turn. If it's still-streaming assistant text, append. If it's a
  // tool, fall through and open a fresh bubble — that way an
  // ``text → tool → text`` flow renders in three rows in the right
  // order, instead of the second text getting merged back into the
  // first bubble (which would visually push the tool below all text).
  for (let i = items.length - 1; i >= 0; i--) {
    const item = items[i];
    if (!item) continue;
    const itemTurn =
      item.kind === "assistant" || item.kind === "tool"
        ? item.turn_request_id
        : null;
    if (itemTurn !== turnId) continue;
    if (item.kind === "assistant") {
      // Late delta after the turn was finalized (gateway/throttle
      // race). Drop it rather than corrupt the finalized text.
      if (!item.streaming) return state;
      items[i] = {
        ...item,
        text: item.text + delta,
        // Stamp the first-token time the moment we get a non-empty delta
        // so the "thought for Ns" badge can use it.
        first_token_at: item.first_token_at ?? Date.now(),
      };
      return { ...state, items };
    }
    // Most recent turn-item is a tool — open a new bubble below it.
    break;
  }
  // Only open a fresh bubble when this delta belongs to the *currently
  // active* turn. A late delta arriving after end_turn (because the gateway
  // and the React render race) would otherwise create a phantom bubble that
  // never finishes streaming.
  if (turnId !== null && state.activeTurn === turnId) {
    const now = Date.now();
    const turnStart = state.turnStartedAt[turnId] ?? now;
    items.push({
      id: nextId(),
      kind: "assistant",
      text: delta,
      streaming: true,
      turn_request_id: turnId,
      // Use the recorded begin_turn time so ``thought for Ns`` shows
      // the real model latency, not 0s.
      started_at: turnStart,
      first_token_at: now,
      finished_at: null,
    });
  }
  return { ...state, items };
}

function openToolCall(
  state: TranscriptState,
  frame: EventFrame,
  turnId: number | null,
): TranscriptState {
  if (turnId === null) return state;
  const parsed = toolCallPayloadSchema.safeParse(frame.payload.tool_call);
  if (!parsed.success) {
    return appendItem(state, {
      id: nextId(),
      kind: "error",
      text: `malformed tool_call payload: ${parsed.error.message}`,
    });
  }
  const tc = parsed.data;
  return appendItem(state, {
    id: nextId(),
    kind: "tool",
    tool_use_id: tc.id,
    name: tc.name,
    args_preview: previewJson(tc.arguments),
    status: "running",
    result_preview: "",
    result_full: "",
    collapsed: false,
    expanded: false,
    started_at: Date.now(),
    finished_at: null,
    turn_request_id: turnId,
  });
}

function closeToolCall(
  state: TranscriptState,
  frame: EventFrame,
  turnId: number | null,
): TranscriptState {
  const parsed = toolResultPayloadSchema.safeParse(frame.payload.tool_result);
  if (!parsed.success) {
    return appendItem(state, {
      id: nextId(),
      kind: "error",
      text: `malformed tool_result payload: ${parsed.error.message}`,
    });
  }
  const result = parsed.data;
  const items = state.items.map((item): TranscriptItem => {
    if (
      item.kind === "tool" &&
      item.tool_use_id === result.tool_use_id &&
      item.turn_request_id === turnId
    ) {
      // Collapse every non-empty non-error result by default; errors
      // collapse only when their payload is long (a 2KB CDP failure
      // dump is no more useful inline than a 2KB success dump). Short
      // errors stay inline so the user reads the message immediately.
      const isLong = result.content.length > 240 || result.content.split("\n").length > 5;
      const collapsed =
        result.content.length > 0 && (!result.is_error || isLong);
      return {
        ...item,
        status: result.is_error ? "error" : "ok",
        result_preview: truncate(result.content, 200),
        result_full: result.content,
        collapsed,
        expanded: false,
        finished_at: Date.now(),
      };
    }
    return item;
  });
  return { ...state, items };
}

function finalizeTurn(
  state: TranscriptState,
  request_id: number,
  final_text: string,
): TranscriptState {
  let foundBubble = false;
  const finishedAt = Date.now();
  const items = state.items.map((item): TranscriptItem => {
    if (item.kind === "assistant" && item.turn_request_id === request_id) {
      foundBubble = true;
      return {
        ...item,
        streaming: false,
        // Trust the server's final content if our streamed buffer is empty
        // (some providers only emit message_done without content_delta).
        text: item.text.length > 0 ? item.text : final_text,
        finished_at: finishedAt,
      };
    }
    return item;
  });
  // If no bubble was ever created (turn was tool-use only with no
  // text reply, or final_text arrived without any content_delta),
  // synthesise one IFF there's actual final_text — otherwise the
  // turn produced no narrative output and we leave the items alone.
  if (!foundBubble && final_text.length > 0) {
    const now = Date.now();
    const turnStart = state.turnStartedAt[request_id] ?? now;
    items.push({
      id: nextId(),
      kind: "assistant",
      text: final_text,
      streaming: false,
      turn_request_id: request_id,
      started_at: turnStart,
      first_token_at: now,
      finished_at: finishedAt,
    });
  }
  // GC the turnStartedAt entry — once the turn ends nothing else
  // needs the timestamp.
  const { [request_id]: _drop, ...remainingStarts } = state.turnStartedAt;
  void _drop;
  return {
    ...state,
    items,
    activeTurn: null,
    turnStartedAt: remainingStarts,
  };
}

function asString(value: unknown): string {
  return typeof value === "string" ? value : JSON.stringify(value ?? "");
}

function previewJson(value: Record<string, unknown> | undefined): string {
  if (!value || Object.keys(value).length === 0) return "";
  const json = JSON.stringify(value);
  return truncate(json, 80);
}

function truncate(text: string, limit: number): string {
  if (text.length <= limit) return text;
  return text.slice(0, limit - 1) + "…";
}
