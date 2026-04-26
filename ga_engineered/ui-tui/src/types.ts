/**
 * UI-side runtime event types (mirror of RuntimeEvent.to_dict() output).
 *
 * The Python backend emits these as the ``payload`` of ``event`` frames
 * whose ``kind`` matches ``RuntimeEventKind``. Two extra non-runtime kinds
 * — ``gateway.ready`` and ``gateway.shutdown`` — bracket the session.
 */

export type RuntimeEventKind =
  | "turn_started"
  | "content_delta"
  | "tool_call"
  | "tool_result"
  | "message_done"
  | "turn_finished"
  | "loop_stopped"
  | "error";

export type GatewayEventKind = "gateway.ready" | "gateway.shutdown";

export type EventKind = RuntimeEventKind | GatewayEventKind;

export interface ToolCall {
  id: string;
  name: string;
  arguments: Record<string, unknown>;
}

export interface ToolResult {
  tool_use_id: string;
  content: string;
  is_error: boolean;
  metadata?: Record<string, unknown>;
}

export interface ChatResponse {
  content: string;
  tool_calls?: ToolCall[];
}

/**
 * Generic runtime-event payload. Fields are unioned per kind because the
 * Python encoder omits keys with empty values.
 */
export interface RuntimeEventPayload {
  kind: RuntimeEventKind;
  delta?: string;
  tool_call?: ToolCall;
  tool_result?: ToolResult;
  response?: ChatResponse;
  error?: string;
  metadata?: Record<string, unknown>;
}

export interface GatewayReadyPayload {
  version: string;
  protocol_version: string;
  pid: number;
}

export interface GatewayShutdownPayload {
  reason: string;
}
