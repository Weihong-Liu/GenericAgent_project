/**
 * Async client for the Python ``generic_agent_engineered.gateway`` server.
 *
 * Spawns the Python backend as a subprocess and speaks line-delimited JSON
 * over its stdin/stdout. RPC calls are Promise-based; runtime events are
 * dispatched to per-kind subscribers. Schema validation runs on every
 * inbound frame so a protocol drift surfaces immediately rather than as a
 * confusing UI bug.
 */

import { ChildProcessWithoutNullStreams, spawn } from "node:child_process";
import { EventEmitter } from "node:events";
import { Readable } from "node:stream";
import { z } from "zod";

import {
  ApprovalDecision,
  ChatApproveResult,
  ChatCancelResult,
  ChatSendResult,
  CommandDispatchResult,
  CommandsListResult,
  EventFrame,
  ExtensionListResult,
  FilesSearchResult,
  IntegrationStatusResult,
  IntegrationsListResult,
  PROTOCOL_MAJOR,
  RuntimeStatus,
  SessionListResult,
  SessionNewResult,
  SessionResumeResult,
  TasksListResult,
  ToolRunResult,
  ToolsListResult,
  WorktreeStatusResult,
  chatApproveResultSchema,
  chatCancelResultSchema,
  chatSendResultSchema,
  commandDispatchResultSchema,
  commandsListResultSchema,
  eventFrameSchema,
  extensionListResultSchema,
  filesSearchResultSchema,
  integrationStatusResultSchema,
  integrationsListResultSchema,
  runtimeStatusSchema,
  sessionListResultSchema,
  sessionNewResultSchema,
  sessionResumeResultSchema,
  tasksListResultSchema,
  toolRunResultSchema,
  toolsListResultSchema,
  worktreeStatusResultSchema,
} from "./schemas.js";

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

// ---------------------------------------------------------------------------
// Frame splitter
// ---------------------------------------------------------------------------

/**
 * Yield complete JSON-line frames from a stream of bytes that may pack or
 * split frames across chunks. Exported for testing.
 */
export class LineSplitter {
  private buffer = "";

  push(chunk: string): string[] {
    this.buffer += chunk;
    const out: string[] = [];
    let idx = this.buffer.indexOf("\n");
    while (idx !== -1) {
      const line = this.buffer.slice(0, idx).trim();
      this.buffer = this.buffer.slice(idx + 1);
      if (line.length > 0) out.push(line);
      idx = this.buffer.indexOf("\n");
    }
    return out;
  }

  flush(): string[] {
    const tail = this.buffer.trim();
    this.buffer = "";
    return tail.length > 0 ? [tail] : [];
  }
}

// ---------------------------------------------------------------------------
// Errors
// ---------------------------------------------------------------------------

export class GatewayError extends Error {
  constructor(
    public readonly code: number,
    message: string,
    public readonly data?: Record<string, unknown>,
  ) {
    super(message);
    this.name = "GatewayError";
  }
}

export class GatewayProtocolError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "GatewayProtocolError";
  }
}

// ---------------------------------------------------------------------------
// Client
// ---------------------------------------------------------------------------

export interface GatewayClientOptions {
  /**
   * Command + args used to launch the backend. Defaults to the local
   * ``python -m generic_agent_engineered.gateway`` invocation, which means
   * the package must be importable on PYTHONPATH (or installed) for the
   * default to work.
   */
  command?: string;
  args?: string[];
  /** Override the child process for unit tests. */
  child?: ChildLike;
  /** Optional environment overlay merged on top of ``process.env``. */
  env?: Record<string, string>;
}

/**
 * Minimal subset of ``ChildProcessWithoutNullStreams`` we need so tests can
 * pass a fake.
 */
export interface ChildLike {
  stdout: NodeJS.ReadableStream;
  stderr: NodeJS.ReadableStream;
  // ``stdin`` only needs to expose ``write`` for our purposes — keeping the
  // surface narrow lets unit tests pass a hand-rolled fake without
  // implementing the full WritableStream contract.
  stdin: { write(chunk: string | Buffer): boolean };
  kill(signal?: NodeJS.Signals | number): boolean;
  on(event: "exit" | "error", listener: (...args: unknown[]) => void): unknown;
}

interface PendingRequest {
  resolve: (result: unknown) => void;
  reject: (error: Error) => void;
}

export type EventListener = (frame: EventFrame) => void;

export class GatewayClient {
  private readonly child: ChildLike;
  private readonly splitter = new LineSplitter();
  private readonly pending = new Map<number, PendingRequest>();
  private readonly emitter = new EventEmitter();
  private readonly stderrChunks: string[] = [];
  private nextId = 1;
  private closed = false;
  private exitReason: string | null = null;
  private readonly readyPromise: Promise<void>;
  private resolveReady!: () => void;
  private rejectReady!: (error: Error) => void;

  constructor(options: GatewayClientOptions = {}) {
    this.readyPromise = new Promise((resolve, reject) => {
      this.resolveReady = resolve;
      this.rejectReady = reject;
    });

    if (options.child) {
      this.child = options.child;
    } else {
      const command = options.command ?? "python3";
      const args = options.args ?? ["-m", "generic_agent_engineered.gateway"];
      const env = { ...process.env, ...(options.env ?? {}) };
      this.child = spawn(command, args, {
        env,
        stdio: ["pipe", "pipe", "pipe"],
      }) as ChildProcessWithoutNullStreams;
    }

    // Many UI components subscribe to events; the default cap of 10 fires a
    // misleading MaxListenersExceededWarning before we've even bootstrapped.
    this.emitter.setMaxListeners(0);

    this.child.stdout.setEncoding?.("utf-8");
    this.child.stderr.setEncoding?.("utf-8");
    this.child.stdout.on("data", (chunk: string) => this.onStdout(chunk));
    this.child.stderr.on("data", (chunk: string) => {
      this.stderrChunks.push(chunk.toString());
    });
    this.child.on("exit", (...args) => {
      const code = args[0];
      this.exitReason = `child exited (code=${code ?? "null"})`;
      this.failPending(this.exitReason);
    });
    this.child.on("error", (...args) => {
      const err = args[0] as Error;
      this.exitReason = `child error: ${err?.message ?? err}`;
      this.rejectReady(new GatewayError(-32099, this.exitReason));
      this.failPending(this.exitReason);
    });

    this.once("gateway.ready", (frame) => {
      const version = (frame.payload.protocol_version as string | undefined) ?? "0.0";
      const major = Number.parseInt(version.split(".")[0] ?? "0", 10);
      if (major !== PROTOCOL_MAJOR) {
        this.rejectReady(
          new GatewayProtocolError(
            `protocol major mismatch: backend=${version}, frontend=${PROTOCOL_MAJOR}.x`,
          ),
        );
        return;
      }
      this.resolveReady();
    });
  }

  // -- public RPC API ------------------------------------------------------

  ready(): Promise<void> {
    return this.readyPromise;
  }

  on(kind: string, listener: EventListener): () => void {
    this.emitter.on(`event:${kind}`, listener);
    return () => this.emitter.off(`event:${kind}`, listener);
  }

  once(kind: string, listener: EventListener): void {
    this.emitter.once(`event:${kind}`, listener);
  }

  async runtimeStatus(): Promise<RuntimeStatus> {
    return this.callValidated("runtime.status", {}, runtimeStatusSchema);
  }

  async commandsList(): Promise<CommandsListResult> {
    return this.callValidated("commands.list", {}, commandsListResultSchema);
  }

  async commandsDispatch(line: string): Promise<CommandDispatchResult> {
    return this.callValidated(
      "commands.dispatch",
      { line },
      commandDispatchResultSchema,
    );
  }

  async toolsList(): Promise<ToolsListResult> {
    return this.callValidated("tools.list", {}, toolsListResultSchema);
  }

  async sessionNew(): Promise<SessionNewResult> {
    return this.callValidated("session.new", {}, sessionNewResultSchema);
  }

  async sessionList(): Promise<SessionListResult> {
    return this.callValidated("session.list", {}, sessionListResultSchema);
  }

  async sessionResume(sessionId: string): Promise<SessionResumeResult> {
    return this.callValidated(
      "session.resume",
      { session_id: sessionId },
      sessionResumeResultSchema,
    );
  }

  async tasksList(): Promise<TasksListResult> {
    return this.callValidated("tasks.list", {}, tasksListResultSchema);
  }

  async worktreeStatus(): Promise<WorktreeStatusResult> {
    return this.callValidated("worktree.status", {}, worktreeStatusResultSchema);
  }

  async mcpList(): Promise<ExtensionListResult> {
    return this.callValidated("mcp.list", {}, extensionListResultSchema);
  }

  async pluginsList(): Promise<ExtensionListResult> {
    return this.callValidated("plugins.list", {}, extensionListResultSchema);
  }

  async agentsList(): Promise<ExtensionListResult> {
    return this.callValidated("agents.list", {}, extensionListResultSchema);
  }

  async hooksList(): Promise<ExtensionListResult> {
    return this.callValidated("hooks.list", {}, extensionListResultSchema);
  }

  async integrationsList(): Promise<IntegrationsListResult> {
    return this.callValidated("integrations.list", {}, integrationsListResultSchema);
  }

  async integrationStatus(name: string): Promise<IntegrationStatusResult> {
    return this.callValidated(
      "integrations.status",
      { name },
      integrationStatusResultSchema,
    );
  }

  /**
   * Issue a chat.send. Returns the ID of the in-flight request so the caller
   * can target ``chatCancel`` at the right turn, and the eventual result
   * promise.
   */
  chatSend(prompt: string): { id: number; result: Promise<ChatSendResult> } {
    const id = this.nextId++;
    const result = this.dispatch<ChatSendResult>(
      id,
      "chat.send",
      { prompt },
      chatSendResultSchema,
    );
    return { id, result };
  }

  async chatCancel(requestId?: number): Promise<ChatCancelResult> {
    const params = requestId === undefined ? {} : { request_id: requestId };
    return this.callValidated("chat.cancel", params, chatCancelResultSchema);
  }

  async toolsRun(name: string, args: Record<string, unknown> = {}): Promise<ToolRunResult> {
    return this.callValidated(
      "tools.run",
      { name, arguments: args },
      toolRunResultSchema,
    );
  }

  async filesSearch(query: string, limit = 25): Promise<FilesSearchResult> {
    return this.callValidated(
      "files.search",
      { query, limit },
      filesSearchResultSchema,
    );
  }

  async chatApprove(
    toolUseId: string,
    decision: ApprovalDecision,
  ): Promise<ChatApproveResult> {
    return this.callValidated(
      "chat.approve",
      { tool_use_id: toolUseId, decision },
      chatApproveResultSchema,
    );
  }

  async shutdown(): Promise<void> {
    if (this.closed) return;
    try {
      await this.call("gateway.shutdown", {});
    } catch {
      // The child may already be dead or the RPC may time out — we still
      // want to release any pending callers and reap the process.
    } finally {
      this.closed = true;
      try {
        this.child.kill();
      } catch {
        // best-effort
      }
      this.detachChildStreams();
      this.failPending("client shut down");
    }
  }

  private detachChildStreams(): void {
    const stdout = this.child.stdout as NodeJS.EventEmitter | undefined;
    const stderr = this.child.stderr as NodeJS.EventEmitter | undefined;
    stdout?.removeAllListeners?.("data");
    stderr?.removeAllListeners?.("data");
  }

  /** Raw stderr buffer, useful for surfacing backend tracebacks to the UI. */
  stderr(): string {
    return this.stderrChunks.join("");
  }

  // -- internals -----------------------------------------------------------

  private async callValidated<T>(
    method: string,
    params: Record<string, unknown>,
    schema: z.ZodType<T>,
  ): Promise<T> {
    const id = this.nextId++;
    return this.dispatch(id, method, params, schema);
  }

  private async call(method: string, params: Record<string, unknown>): Promise<unknown> {
    const id = this.nextId++;
    return new Promise<unknown>((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.write({ type: "request", id, method, params });
    });
  }

  private dispatch<T>(
    id: number,
    method: string,
    params: Record<string, unknown>,
    schema: z.ZodType<T>,
  ): Promise<T> {
    return new Promise<T>((resolve, reject) => {
      this.pending.set(id, {
        resolve: (raw) => {
          const parsed = schema.safeParse(raw);
          if (!parsed.success) {
            reject(
              new GatewayProtocolError(
                `invalid result shape for ${method}: ${parsed.error.message}`,
              ),
            );
            return;
          }
          resolve(parsed.data);
        },
        reject,
      });
      this.write({ type: "request", id, method, params });
    });
  }

  private write(frame: Record<string, unknown>): void {
    if (this.closed) {
      throw new GatewayError(-32099, "gateway client is closed");
    }
    const line = JSON.stringify(frame) + "\n";
    this.child.stdin.write(line);
  }

  private onStdout(chunk: string): void {
    for (const line of this.splitter.push(chunk)) {
      this.handleLine(line);
    }
  }

  private handleLine(line: string): void {
    let raw: unknown;
    try {
      raw = JSON.parse(line);
    } catch (exc) {
      this.emitFrontendError(`frontend failed to parse line: ${(exc as Error).message}`);
      return;
    }

    if (!isObject(raw)) {
      this.emitFrontendError("frontend rejected frame: not a JSON object");
      return;
    }

    if (raw["type"] === "response") {
      this.handleResponse(raw);
      return;
    }
    if (raw["type"] === "event") {
      const parsed = eventFrameSchema.safeParse(raw);
      if (!parsed.success) {
        this.emitFrontendError(`frontend rejected event: ${parsed.error.message}`);
        return;
      }
      this.handleEvent(parsed.data);
      return;
    }
    this.emitFrontendError(`frontend rejected frame: unknown type ${String(raw["type"])}`);
  }

  private handleResponse(raw: Record<string, unknown>): void {
    const id = raw["id"];
    if (typeof id !== "number") return;
    const pending = this.pending.get(id);
    if (!pending) return;
    this.pending.delete(id);

    if ("error" in raw && isObject(raw["error"])) {
      const errorRaw = raw["error"] as Record<string, unknown>;
      pending.reject(
        new GatewayError(
          Number(errorRaw["code"] ?? -32099),
          String(errorRaw["message"] ?? "unknown error"),
          isObject(errorRaw["data"]) ? (errorRaw["data"] as Record<string, unknown>) : undefined,
        ),
      );
      return;
    }
    pending.resolve(raw["result"]);
  }

  private emitFrontendError(message: string): void {
    this.emitter.emit(
      "event:error",
      {
        type: "event",
        kind: "error",
        payload: { error: message },
      } satisfies EventFrame,
    );
  }

  private handleEvent(frame: EventFrame): void {
    this.emitter.emit(`event:${frame.kind}`, frame);
    this.emitter.emit("event:*", frame);
  }

  private failPending(reason: string): void {
    for (const pending of this.pending.values()) {
      pending.reject(new GatewayError(-32099, reason));
    }
    this.pending.clear();
  }
}

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

/**
 * In-memory fake child process useful for unit-testing the client without
 * spawning Python. Frames written to ``stdin`` are appended to ``written``;
 * scripted frames can be pushed back through ``feedFrame``.
 */
export class FakeChild implements ChildLike {
  readonly stdout: Readable;
  readonly stderr: Readable;
  readonly stdin: { write: (chunk: string | Buffer) => boolean };
  readonly written: string[] = [];
  private listeners: Record<string, Array<(...args: unknown[]) => void>> = {};

  constructor() {
    this.stdout = new Readable({ read() {} });
    this.stdout.setEncoding("utf-8");
    this.stderr = new Readable({ read() {} });
    this.stderr.setEncoding("utf-8");
    this.stdin = {
      write: (chunk) => {
        this.written.push(chunk.toString());
        return true;
      },
    };
  }

  on(event: "exit" | "error", listener: (...args: unknown[]) => void): this {
    (this.listeners[event] ??= []).push(listener);
    return this;
  }

  emit(event: "exit" | "error", ...args: unknown[]): void {
    for (const fn of this.listeners[event] ?? []) {
      fn(...args);
    }
  }

  feedRaw(text: string): void {
    this.stdout.push(text);
  }

  feedFrame(frame: Record<string, unknown>): void {
    this.feedRaw(JSON.stringify(frame) + "\n");
  }

  feedReady(): void {
    this.feedFrame({
      type: "event",
      kind: "gateway.ready",
      payload: { version: "0.1.0", protocol_version: "1.0", pid: 99999 },
    });
  }

  closeStdout(): void {
    this.stdout.push(null);
  }

  kill(): boolean {
    this.closeStdout();
    return true;
  }
}
