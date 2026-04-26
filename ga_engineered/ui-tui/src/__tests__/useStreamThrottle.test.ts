/**
 * Replay the throttle's setTimeout-based merging via a tiny pure model.
 * The hook's actual setTimeout interaction is verified manually; this
 * model captures the merge semantics — pushed strings concatenate
 * until a flush, after which the buffer is empty.
 */

import { describe, expect, it } from "vitest";

class Throttle {
  private pending = "";
  private timer: ReturnType<typeof setTimeout> | null = null;
  private intervalMs: number;
  private onFlush: (text: string) => void;

  constructor(onFlush: (text: string) => void, intervalMs = 16) {
    this.onFlush = onFlush;
    this.intervalMs = intervalMs;
  }

  push(text: string): void {
    if (text.length === 0) return;
    this.pending += text;
    if (this.timer) return;
    this.timer = setTimeout(() => {
      this.timer = null;
      const merged = this.pending;
      if (merged.length === 0) return;
      this.pending = "";
      this.onFlush(merged);
    }, this.intervalMs);
  }

  flush(): void {
    if (this.timer) {
      clearTimeout(this.timer);
      this.timer = null;
    }
    if (this.pending.length === 0) return;
    const text = this.pending;
    this.pending = "";
    this.onFlush(text);
  }
}

describe("useStreamThrottle model", () => {
  it("merges multiple pushes into one flush", async () => {
    const flushed: string[] = [];
    const t = new Throttle((s) => flushed.push(s), 5);
    t.push("a");
    t.push("b");
    t.push("c");
    await new Promise((r) => setTimeout(r, 30));
    expect(flushed).toEqual(["abc"]);
  });

  it("flush() drains pending text immediately", () => {
    const flushed: string[] = [];
    const t = new Throttle((s) => flushed.push(s), 100);
    t.push("hi");
    t.flush();
    expect(flushed).toEqual(["hi"]);
  });

  it("ignores empty pushes", () => {
    const flushed: string[] = [];
    const t = new Throttle((s) => flushed.push(s));
    t.push("");
    t.flush();
    expect(flushed).toEqual([]);
  });

  it("subsequent pushes after flush start a new batch", async () => {
    const flushed: string[] = [];
    const t = new Throttle((s) => flushed.push(s), 5);
    t.push("a");
    await new Promise((r) => setTimeout(r, 20));
    t.push("b");
    await new Promise((r) => setTimeout(r, 20));
    expect(flushed).toEqual(["a", "b"]);
  });
});
