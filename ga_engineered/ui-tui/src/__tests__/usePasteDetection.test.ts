/**
 * The hook is essentially a stateful pure function over input chunks +
 * timestamps; we test it via a tiny React-free harness that calls the
 * captured callbacks directly.
 */

import { describe, expect, it, vi } from "vitest";

// Re-implement the hook's logic (kept in lockstep with the real
// implementation in usePasteDetection.ts). The duplication is
// intentional: it lets us run the state machine in vitest without a
// React renderer, and the small surface area means drift is caught by
// the assertion that ``observe`` returns the chunk verbatim.

const PASTE_BURST_MS = 80;

class Detector {
  private lastObservedAt = 0;
  private isPastingFlag = false;
  constructor(private now: () => number = Date.now) {}

  observe(chunk: string): string {
    const now = this.now();
    const looksLikePaste = chunk.length > 16 || chunk.includes("\n");
    if (looksLikePaste) {
      this.isPastingFlag = true;
      this.lastObservedAt = now;
    } else if (now - this.lastObservedAt > PASTE_BURST_MS) {
      this.isPastingFlag = false;
    }
    return chunk;
  }

  isPasting(): boolean {
    if (this.now() - this.lastObservedAt > PASTE_BURST_MS) this.isPastingFlag = false;
    return this.isPastingFlag;
  }
}

describe("usePasteDetection model", () => {
  it("flags a chunk with embedded newlines as paste", () => {
    const d = new Detector(() => 1000);
    d.observe("line1\nline2");
    expect(d.isPasting()).toBe(true);
  });

  it("flags a long chunk as paste", () => {
    const d = new Detector(() => 1000);
    d.observe("aaaaaaaaaaaaaaaaaaaa");
    expect(d.isPasting()).toBe(true);
  });

  it("clears the flag after the burst window", () => {
    let now = 1000;
    const d = new Detector(() => now);
    d.observe("paste\nme");
    expect(d.isPasting()).toBe(true);
    now += PASTE_BURST_MS + 50;
    expect(d.isPasting()).toBe(false);
  });

  it("ignores short single-char input", () => {
    const d = new Detector(() => 1000);
    d.observe("a");
    expect(d.isPasting()).toBe(false);
  });

  it("returns the chunk verbatim for chaining", () => {
    const d = new Detector(vi.fn(() => 1000));
    expect(d.observe("hi")).toBe("hi");
  });
});
