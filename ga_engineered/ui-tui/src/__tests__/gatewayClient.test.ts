import { afterEach, beforeEach, describe, expect, it } from "vitest";

import {
  FakeChild,
  GatewayClient,
  GatewayError,
  GatewayProtocolError,
  LineSplitter,
} from "../gatewayClient.js";

describe("LineSplitter", () => {
  it("yields complete lines from a single chunk", () => {
    const splitter = new LineSplitter();
    const lines = splitter.push('{"a":1}\n{"b":2}\n');
    expect(lines).toEqual(['{"a":1}', '{"b":2}']);
  });

  it("handles split frames across chunks", () => {
    const splitter = new LineSplitter();
    expect(splitter.push('{"a":')).toEqual([]);
    expect(splitter.push('1}\n{"b"')).toEqual(['{"a":1}']);
    expect(splitter.push(":2}\n")).toEqual(['{"b":2}']);
  });

  it("ignores blank lines", () => {
    const splitter = new LineSplitter();
    expect(splitter.push("\n\n\n")).toEqual([]);
  });

  it("flush returns trailing incomplete frame as last line", () => {
    const splitter = new LineSplitter();
    splitter.push("partial");
    expect(splitter.flush()).toEqual(["partial"]);
  });
});

describe("GatewayClient", () => {
  let child: FakeChild;
  let client: GatewayClient;

  beforeEach(() => {
    child = new FakeChild();
    client = new GatewayClient({ child });
  });

  afterEach(() => {
    child.kill();
  });

  it("ready resolves when gateway.ready event arrives", async () => {
    child.feedReady();
    await expect(client.ready()).resolves.toBeUndefined();
  });

  it("ready rejects on protocol major mismatch", async () => {
    child.feedFrame({
      type: "event",
      kind: "gateway.ready",
      payload: { version: "0.1.0", protocol_version: "2.0", pid: 1 },
    });
    await expect(client.ready()).rejects.toBeInstanceOf(GatewayProtocolError);
  });

  it("runtimeStatus round-trips through JSON-RPC", async () => {
    child.feedReady();
    await client.ready();

    const promise = client.runtimeStatus();

    // The client wrote one frame; capture its id and reply.
    const written = JSON.parse(child.written[0] as string);
    expect(written.method).toBe("runtime.status");
    child.feedFrame({
      type: "response",
      id: written.id,
      result: {
        protocol_version: "1.0",
        gateway_version: "0.1.0",
        provider: "anthropic",
        model: "x",
        session_id: "default",
        turn_count: 0,
        max_turns: 8,
        tokens_used: 0,
        tokens_budget: null,
        tool_count: 3,
        skill_count: 0,
        busy: false,
      },
    });

    const status = await promise;
    expect(status.provider).toBe("anthropic");
    expect(status.tool_count).toBe(3);
  });

  it("error responses become GatewayError", async () => {
    child.feedReady();
    await client.ready();

    const promise = client.runtimeStatus();
    const written = JSON.parse(child.written[0] as string);
    child.feedFrame({
      type: "response",
      id: written.id,
      error: { code: -32099, message: "boom" },
    });

    await expect(promise).rejects.toBeInstanceOf(GatewayError);
    await promise.catch((exc: GatewayError) => {
      expect(exc.code).toBe(-32099);
      expect(exc.message).toBe("boom");
    });
  });

  it("malformed result shape rejects with protocol error", async () => {
    child.feedReady();
    await client.ready();

    const promise = client.runtimeStatus();
    const written = JSON.parse(child.written[0] as string);
    child.feedFrame({
      type: "response",
      id: written.id,
      result: { provider: 42 }, // wrong type, missing fields
    });

    await expect(promise).rejects.toBeInstanceOf(GatewayProtocolError);
  });

  it("dispatches events to per-kind subscribers", async () => {
    child.feedReady();
    await client.ready();

    const captured: unknown[] = [];
    client.on("content_delta", (frame) => captured.push(frame.payload.delta));

    child.feedFrame({
      type: "event",
      kind: "content_delta",
      payload: { kind: "content_delta", delta: "hi" },
      request_id: 1,
    });

    expect(captured).toEqual(["hi"]);
  });

  it("invalid frames surface as error events, not exceptions", async () => {
    child.feedReady();
    await client.ready();

    const captured: unknown[] = [];
    client.on("error", (frame) => captured.push(frame.payload.error));

    child.feedRaw("not-json\n");
    expect(captured.length).toBe(1);
    expect(String(captured[0])).toContain("frontend failed to parse");
  });

  it("chatSend yields the request id used in the wire frame", async () => {
    child.feedReady();
    await client.ready();

    const { id } = client.chatSend("hi");
    const written = JSON.parse(child.written[0] as string);
    expect(written.method).toBe("chat.send");
    expect(written.id).toBe(id);
    expect(written.params).toEqual({ prompt: "hi" });
  });

  it("sessionList and sessionResume round-trip through JSON-RPC", async () => {
    child.feedReady();
    await client.ready();

    const listPromise = client.sessionList();
    const listFrame = JSON.parse(child.written[0] as string);
    expect(listFrame.method).toBe("session.list");
    child.feedFrame({
      type: "response",
      id: listFrame.id,
      result: {
        current_session_id: "default",
        sessions: [
          {
            id: "default",
            title: "default",
            parent_session_id: null,
            provider: "openai",
            model: "gpt-5.4",
            created_at: "",
            updated_at: "",
            message_count: 0,
            current: true,
            persisted: false,
          },
        ],
      },
    });
    expect((await listPromise).sessions[0]?.id).toBe("default");

    const resumePromise = client.sessionResume("default");
    const resumeFrame = JSON.parse(child.written[1] as string);
    expect(resumeFrame.method).toBe("session.resume");
    expect(resumeFrame.params).toEqual({ session_id: "default" });
    child.feedFrame({
      type: "response",
      id: resumeFrame.id,
      result: {
        session_id: "default",
        turn_count: 0,
        messages: 0,
        session: {
          id: "default",
          title: "default",
          parent_session_id: null,
          provider: "openai",
          model: "gpt-5.4",
          created_at: "",
          updated_at: "",
          message_count: 0,
          current: true,
          persisted: false,
        },
      },
    });
    expect((await resumePromise).session_id).toBe("default");
  });

  it("tasksList and worktreeStatus validate panel result shapes", async () => {
    child.feedReady();
    await client.ready();

    const tasksPromise = client.tasksList();
    const tasksFrame = JSON.parse(child.written[0] as string);
    expect(tasksFrame.method).toBe("tasks.list");
    child.feedFrame({
      type: "response",
      id: tasksFrame.id,
      result: {
        busy: true,
        in_flight_request_id: 7,
        tasks: [{ id: "7", label: "chat.send", status: "running", detail: "turn" }],
      },
    });
    expect((await tasksPromise).tasks[0]?.status).toBe("running");

    const worktreePromise = client.worktreeStatus();
    const worktreeFrame = JSON.parse(child.written[1] as string);
    expect(worktreeFrame.method).toBe("worktree.status");
    child.feedFrame({
      type: "response",
      id: worktreeFrame.id,
      result: {
        is_git: true,
        path: "/repo",
        branch: "main",
        dirty: false,
        changes: 0,
        ahead: 0,
        behind: 0,
      },
    });
    expect((await worktreePromise).branch).toBe("main");
  });

  it("extension list methods use dedicated JSON-RPC names", async () => {
    child.feedReady();
    await client.ready();

    const calls = [
      [client.mcpList(), "mcp.list"],
      [client.pluginsList(), "plugins.list"],
      [client.agentsList(), "agents.list"],
      [client.hooksList(), "hooks.list"],
    ] as const;

    calls.forEach(([_promise, method], index) => {
      const frame = JSON.parse(child.written[index] as string);
      expect(frame.method).toBe(method);
      child.feedFrame({
        type: "response",
        id: frame.id,
        result: { kind: method.split(".")[0], items: [] },
      });
    });

    await expect(calls[0][0]).resolves.toEqual({ kind: "mcp", items: [] });
    await expect(calls[1][0]).resolves.toEqual({ kind: "plugins", items: [] });
    await expect(calls[2][0]).resolves.toEqual({ kind: "agents", items: [] });
    await expect(calls[3][0]).resolves.toEqual({ kind: "hooks", items: [] });
  });

  it("integration methods validate dedicated JSON-RPC result shapes", async () => {
    child.feedReady();
    await client.ready();

    const listPromise = client.integrationsList();
    const listFrame = JSON.parse(child.written[0] as string);
    expect(listFrame.method).toBe("integrations.list");
    child.feedFrame({
      type: "response",
      id: listFrame.id,
      result: {
        integrations: [
          {
            name: "chrome",
            label: "Chrome bridge",
            status: "available",
            available: true,
            detail: "extension=present",
            action: "Run `gae bridge`.",
          },
        ],
      },
    });
    expect((await listPromise).integrations[0]?.name).toBe("chrome");

    const statusPromise = client.integrationStatus("voice");
    const statusFrame = JSON.parse(child.written[1] as string);
    expect(statusFrame.method).toBe("integrations.status");
    expect(statusFrame.params).toEqual({ name: "voice" });
    child.feedFrame({
      type: "response",
      id: statusFrame.id,
      result: {
        integration: {
          name: "voice",
          label: "Voice input",
          status: "unavailable",
          available: false,
          detail: "not wired",
          action: "Voice capture is not wired.",
        },
      },
    });
    expect((await statusPromise).integration.available).toBe(false);
  });

  it("ready rejects when child errors during startup", async () => {
    child.emit("error", new Error("nope"));
    await expect(client.ready()).rejects.toBeInstanceOf(GatewayError);
  });
});
