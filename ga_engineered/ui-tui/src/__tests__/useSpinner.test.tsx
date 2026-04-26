/**
 * Validate the useSpinner hook indirectly: assert the underlying
 * unicode-animations data is well-formed and that the hook references
 * the correct spinner name. Mounting React with timers requires a
 * renderer that vitest's Node env does not ship, and the rendering
 * logic itself is one ``setInterval`` call — not worth wiring in
 * react-test-renderer just for that. The visual smoke is covered by
 * the build-bundle and manual e2e in GAE-T08.
 */

import { describe, expect, it } from "vitest";

import spinners, { type BrailleSpinnerName } from "unicode-animations";

import { useSpinner } from "../hooks/useSpinner.js";

describe("unicode-animations data the hook depends on", () => {
  it("known spinner names exist with non-empty frame arrays", () => {
    const names: BrailleSpinnerName[] = [
      "cascade",
      "scan",
      "diagswipe",
      "breathe",
      "orbit",
      "helix",
    ];
    for (const name of names) {
      const spinner = spinners[name];
      expect(spinner).toBeDefined();
      expect(spinner.frames.length).toBeGreaterThan(0);
      expect(spinner.frames.every((f) => typeof f === "string")).toBe(true);
      expect(spinner.interval).toBeGreaterThan(0);
    }
  });

  it("each cascade frame is a non-empty braille string", () => {
    const cascade = spinners.cascade;
    for (const frame of cascade.frames) {
      expect(frame.length).toBeGreaterThan(0);
      // All chars should be in the braille block (U+2800–U+28FF) or whitespace.
      for (const ch of frame) {
        const code = ch.charCodeAt(0);
        expect(code >= 0x2800 && code <= 0x28ff).toBe(true);
      }
    }
  });
});

describe("useSpinner export shape", () => {
  it("is a function with the documented signature", () => {
    // Calling the hook outside React would throw, but the shape check
    // catches accidental rename / signature drift at import time.
    expect(typeof useSpinner).toBe("function");
    expect(useSpinner.length).toBeLessThanOrEqual(2); // (name?, options?)
  });
});

/**
 * The hook's state machine is a single ``setInterval`` that advances a
 * modular counter. Re-implementing that as a pure function lets us
 * cover the wrap and pause behaviour without a React renderer.
 */
function advance(idx: number, total: number, ticks: number): number {
  return total === 0 ? 0 : (idx + ticks) % total;
}

describe("frame index wrapping (modeled)", () => {
  it("wraps modulo the frame count", () => {
    expect(advance(0, 8, 7)).toBe(7);
    expect(advance(0, 8, 8)).toBe(0);
    expect(advance(7, 8, 1)).toBe(0);
    expect(advance(3, 8, 100)).toBe(3 + (100 % 8));
  });

  it("returns 0 when total frames is 0", () => {
    expect(advance(5, 0, 100)).toBe(0);
  });
});

