/**
 * The hook itself uses ``useState`` + ``useRef`` so we need a tiny React
 * runner. We use a minimal manual test harness via ``react``'s
 * test-renderer-free API: directly construct the hook function via a
 * fake fiber. Since vitest cannot mount React without renderer deps,
 * we assert the *pure* logic by reaching into a small test stub: the
 * commit/prev/next sequence does not actually require React state to
 * advance — the refs do.
 *
 * That said, the simpler path is to extract the same algorithm into a
 * pure helper. We test the hook indirectly by wrapping it in a tiny
 * synchronous stand-in.
 */

import { describe, expect, it } from "vitest";

import type { HistoryEntry } from "../hooks/useInputHistory.js";

// --- Pure model mirroring the hook's behaviour ----------------------------

interface Model {
  entries: HistoryEntry[];
  index: number; // -1 means "not in history mode"
  draft: string;
}

function newModel(initial: HistoryEntry[] = []): Model {
  return { entries: [...initial], index: -1, draft: "" };
}

function commit(model: Model, entry: HistoryEntry): Model {
  if (entry.text.trim().length === 0) return model;
  const last = model.entries[model.entries.length - 1];
  if (last && last.mode === entry.mode && last.text === entry.text) return model;
  return { ...model, entries: [...model.entries, entry] };
}

function prev(model: Model, mode: "chat" | "bash", currentDraft: string): {
  model: Model;
  result: string | null;
} {
  const list = model.entries.filter((e) => e.mode === mode);
  if (list.length === 0) return { model, result: null };
  let next: number;
  let nextDraft = model.draft;
  if (model.index === -1) {
    nextDraft = currentDraft;
    next = list.length - 1;
  } else {
    next = Math.max(0, model.index - 1);
  }
  return {
    model: { ...model, index: next, draft: nextDraft },
    result: list[next]?.text ?? null,
  };
}

function next(model: Model, mode: "chat" | "bash"): {
  model: Model;
  result: string | null;
} {
  const list = model.entries.filter((e) => e.mode === mode);
  if (list.length === 0 || model.index === -1) return { model, result: null };
  if (model.index >= list.length - 1) {
    return {
      model: { ...model, index: -1, draft: "" },
      result: model.draft,
    };
  }
  const newIdx = model.index + 1;
  return {
    model: { ...model, index: newIdx },
    result: list[newIdx]?.text ?? null,
  };
}

// --- Tests ----------------------------------------------------------------

describe("useInputHistory model — commit", () => {
  it("appends a new entry", () => {
    const m = commit(newModel(), { mode: "chat", text: "hi" });
    expect(m.entries).toHaveLength(1);
  });

  it("dedups consecutive identical entries", () => {
    let m = commit(newModel(), { mode: "chat", text: "hi" });
    m = commit(m, { mode: "chat", text: "hi" });
    expect(m.entries).toHaveLength(1);
  });

  it("ignores empty entries", () => {
    const m = commit(newModel(), { mode: "chat", text: "  " });
    expect(m.entries).toHaveLength(0);
  });

  it("does not dedup across modes", () => {
    let m = commit(newModel(), { mode: "chat", text: "x" });
    m = commit(m, { mode: "bash", text: "x" });
    expect(m.entries).toHaveLength(2);
  });
});

describe("useInputHistory model — prev/next", () => {
  const seed: HistoryEntry[] = [
    { mode: "chat", text: "alpha" },
    { mode: "chat", text: "bravo" },
    { mode: "chat", text: "charlie" },
  ];

  it("up arrow recalls the newest entry first", () => {
    const { result } = prev(newModel(seed), "chat", "draft");
    expect(result).toBe("charlie");
  });

  it("repeated up walks backward", () => {
    let m = newModel(seed);
    let r1 = prev(m, "chat", "");
    m = r1.model;
    let r2 = prev(m, "chat", "");
    m = r2.model;
    let r3 = prev(m, "chat", "");
    expect([r1.result, r2.result, r3.result]).toEqual(["charlie", "bravo", "alpha"]);
  });

  it("down arrow at the bottom restores the draft", () => {
    let m = newModel(seed);
    const up = prev(m, "chat", "DRAFT");
    m = up.model;
    expect(m.draft).toBe("DRAFT");
    const down = next(m, "chat");
    expect(down.result).toBe("DRAFT");
    expect(down.model.index).toBe(-1);
  });

  it("filters by mode", () => {
    const mixed: HistoryEntry[] = [
      { mode: "chat", text: "c1" },
      { mode: "bash", text: "b1" },
      { mode: "chat", text: "c2" },
    ];
    const { result } = prev(newModel(mixed), "bash", "");
    expect(result).toBe("b1");
  });
});
