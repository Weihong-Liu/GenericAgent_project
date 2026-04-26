/**
 * Runtime validators that mirror the Python wire types.
 *
 * Source of truth: ../../../tasks/TUI_TS_PROTOCOL.md (and the
 * dataclasses in src/generic_agent_engineered/gateway/protocol.py and
 * src/generic_agent_engineered/runtime/events.py).
 *
 * Drift between this file and the Python side will silently break event
 * parsing. Any new method or event kind must be added in lockstep with
 * the protocol doc and the gateway server.
 */

import { z } from "zod";

export const PROTOCOL_MAJOR = 1;

// ---------------------------------------------------------------------------
// Frame envelopes
// ---------------------------------------------------------------------------

export const responseSuccessSchema = z.object({
  type: z.literal("response"),
  id: z.number().int(),
  result: z.unknown(),
});

export const responseErrorSchema = z.object({
  type: z.literal("response"),
  id: z.number().int(),
  error: z.object({
    code: z.number().int(),
    message: z.string(),
    data: z.record(z.string(), z.unknown()).optional(),
  }),
});

// We do NOT use z.union here because both branches are structurally
// compatible (both have type/id, the success branch's ``result`` accepts
// undefined). Instead the gateway client peeks at the ``error`` field
// before choosing which schema to validate against.
export const responseFrameSchema = z.union([
  responseErrorSchema,
  responseSuccessSchema,
]);

export const eventFrameSchema = z.object({
  type: z.literal("event"),
  kind: z.string(),
  payload: z.record(z.string(), z.unknown()),
  request_id: z.number().int().optional(),
});

export const inboundFrameSchema = z.union([responseFrameSchema, eventFrameSchema]);

// ---------------------------------------------------------------------------
// Per-event payload validators (used by the transcript reducer)
// ---------------------------------------------------------------------------

export const toolCallPayloadSchema = z.object({
  id: z.string(),
  name: z.string(),
  arguments: z.record(z.string(), z.unknown()),
});

export const toolResultPayloadSchema = z.object({
  tool_use_id: z.string(),
  content: z.string(),
  is_error: z.boolean(),
  metadata: z.record(z.string(), z.unknown()).optional(),
});

export type ToolCallPayload = z.infer<typeof toolCallPayloadSchema>;
export type ToolResultPayload = z.infer<typeof toolResultPayloadSchema>;

export type ResponseFrame = z.infer<typeof responseFrameSchema>;
export type EventFrame = z.infer<typeof eventFrameSchema>;
export type InboundFrame = z.infer<typeof inboundFrameSchema>;

// ---------------------------------------------------------------------------
// Method results
// ---------------------------------------------------------------------------

export const chatSendStatusSchema = z.enum([
  "completed",
  "max_turns_exceeded",
  "cancelled",
  "stopped",
  "error",
  "empty_prompt",
]);

export const chatSendResultSchema = z.object({
  status: chatSendStatusSchema,
  content: z.string(),
  is_error: z.boolean(),
  turn_count: z.number().int().nonnegative(),
  provider: z.string(),
  model: z.string(),
  // ``.nullish()`` accepts both ``null`` and a missing key — the Python side
  // currently always sends ``null``, but tolerating omission keeps us
  // robust to a future gateway change that drops empty fields entirely.
  error_type: z.string().nullish(),
  retry_reason: z.string().nullish(),
});

export const commandDefSchema = z.object({
  name: z.string(),
  description: z.string(),
  category: z.string(),
  aliases: z.array(z.string()),
  args_hint: z.string(),
  subcommands: z.array(z.string()),
  cli_only: z.boolean(),
});

export const commandsListResultSchema = z.object({
  commands: z.array(commandDefSchema),
});

export const commandDispatchResultSchema = z.object({
  content: z.string(),
  is_error: z.boolean(),
  should_exit: z.boolean(),
  metadata: z.record(z.string(), z.unknown()),
});

export const toolPermissionSchema = z.object({
  name: z.string(),
  reason: z.string(),
});

export const toolSpecSchema = z.object({
  name: z.string(),
  description: z.string(),
  enabled: z.boolean(),
  schema: z.record(z.string(), z.unknown()),
  permissions: z.array(toolPermissionSchema),
});

export const toolsListResultSchema = z.object({
  tools: z.array(toolSpecSchema),
});

export const runtimeStatusSchema = z.object({
  protocol_version: z.string(),
  gateway_version: z.string(),
  provider: z.string(),
  model: z.string(),
  session_id: z.string(),
  turn_count: z.number().int().nonnegative(),
  max_turns: z.number().int().positive(),
  tokens_used: z.number().int().nonnegative(),
  tokens_budget: z.number().int().nullable(),
  tool_count: z.number().int().nonnegative(),
  skill_count: z.number().int().nonnegative(),
  busy: z.boolean(),
  // Optional so older gateways without the auto-bridge feature still
  // pass validation.
  bridge_running: z.boolean().optional(),
});

export const sessionNewResultSchema = z.object({
  turn_count: z.number().int().nonnegative(),
  session_id: z.string(),
});

export const sessionSummarySchema = z.object({
  id: z.string(),
  title: z.string(),
  parent_session_id: z.string().nullable(),
  provider: z.string(),
  model: z.string(),
  created_at: z.string(),
  updated_at: z.string(),
  message_count: z.number().int().nonnegative(),
  current: z.boolean(),
  persisted: z.boolean(),
});

export const sessionListResultSchema = z.object({
  current_session_id: z.string(),
  sessions: z.array(sessionSummarySchema),
});

export const sessionResumeResultSchema = z.object({
  session_id: z.string(),
  turn_count: z.number().int().nonnegative(),
  messages: z.number().int().nonnegative(),
  session: sessionSummarySchema,
});

export const backgroundTaskSchema = z.object({
  id: z.string(),
  label: z.string(),
  status: z.string(),
  detail: z.string(),
});

export const tasksListResultSchema = z.object({
  busy: z.boolean(),
  in_flight_request_id: z.number().int().nullable(),
  tasks: z.array(backgroundTaskSchema),
});

export const worktreeStatusResultSchema = z.object({
  is_git: z.boolean(),
  path: z.string(),
  branch: z.string(),
  dirty: z.boolean(),
  changes: z.number().int().nonnegative(),
  ahead: z.number().int().nonnegative(),
  behind: z.number().int().nonnegative(),
});

export const extensionSummarySchema = z.object({
  name: z.string(),
  kind: z.string(),
  status: z.string(),
  source: z.string(),
  detail: z.string(),
});

export const extensionListResultSchema = z.object({
  kind: z.string(),
  items: z.array(extensionSummarySchema),
});

export const integrationStatusSchema = z.object({
  name: z.string(),
  label: z.string(),
  status: z.string(),
  available: z.boolean(),
  detail: z.string(),
  action: z.string(),
});

export const integrationsListResultSchema = z.object({
  integrations: z.array(integrationStatusSchema),
});

export const integrationStatusResultSchema = z.object({
  integration: integrationStatusSchema,
});

export const chatCancelResultSchema = z.object({
  cancelled: z.boolean(),
  request_id: z.number().int().optional(),
});

export const toolRunResultSchema = z.object({
  tool_use_id: z.string(),
  content: z.string(),
  is_error: z.boolean(),
  metadata: z.record(z.string(), z.unknown()).optional(),
});

export const fileMatchSchema = z.object({ path: z.string() });
export const filesSearchResultSchema = z.object({
  matches: z.array(fileMatchSchema),
});

export const approvalRequestPayloadSchema = z.object({
  tool_use_id: z.string(),
  name: z.string(),
  arguments_preview: z.string(),
});

export const chatApproveResultSchema = z.object({
  resolved: z.boolean(),
  decision: z.enum(["allow_once", "allow_always", "deny"]),
});

export type ApprovalRequestPayload = z.infer<typeof approvalRequestPayloadSchema>;
export type ChatApproveResult = z.infer<typeof chatApproveResultSchema>;
export type ApprovalDecision = ChatApproveResult["decision"];

export type ToolRunResult = z.infer<typeof toolRunResultSchema>;
export type FilesSearchResult = z.infer<typeof filesSearchResultSchema>;

// ---------------------------------------------------------------------------
// Inferred TS types (used everywhere in the app)
// ---------------------------------------------------------------------------

export type ChatSendStatus = z.infer<typeof chatSendStatusSchema>;
export type ChatSendResult = z.infer<typeof chatSendResultSchema>;
export type CommandDef = z.infer<typeof commandDefSchema>;
export type CommandsListResult = z.infer<typeof commandsListResultSchema>;
export type CommandDispatchResult = z.infer<typeof commandDispatchResultSchema>;
export type ToolPermission = z.infer<typeof toolPermissionSchema>;
export type ToolSpec = z.infer<typeof toolSpecSchema>;
export type ToolsListResult = z.infer<typeof toolsListResultSchema>;
export type RuntimeStatus = z.infer<typeof runtimeStatusSchema>;
export type SessionNewResult = z.infer<typeof sessionNewResultSchema>;
export type SessionSummary = z.infer<typeof sessionSummarySchema>;
export type SessionListResult = z.infer<typeof sessionListResultSchema>;
export type SessionResumeResult = z.infer<typeof sessionResumeResultSchema>;
export type BackgroundTask = z.infer<typeof backgroundTaskSchema>;
export type TasksListResult = z.infer<typeof tasksListResultSchema>;
export type WorktreeStatusResult = z.infer<typeof worktreeStatusResultSchema>;
export type ExtensionSummary = z.infer<typeof extensionSummarySchema>;
export type ExtensionListResult = z.infer<typeof extensionListResultSchema>;
export type IntegrationStatus = z.infer<typeof integrationStatusSchema>;
export type IntegrationsListResult = z.infer<typeof integrationsListResultSchema>;
export type IntegrationStatusResult = z.infer<typeof integrationStatusResultSchema>;
export type ChatCancelResult = z.infer<typeof chatCancelResultSchema>;
