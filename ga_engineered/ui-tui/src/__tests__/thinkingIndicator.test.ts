import { describe, expect, it } from "vitest";

import {
  formatDuration,
  formatTokens,
} from "../components/thinkingIndicator.js";
import { SPINNER_VERBS, pickVerb } from "../spinnerVerbs.js";

describe("formatDuration", () => {
  it("renders sub-minute as ``Ns``", () => {
    expect(formatDuration(0)).toBe("0s");
    expect(formatDuration(14_000)).toBe("14s");
    expect(formatDuration(59_999)).toBe("59s");
  });

  it("collapses zero-second minutes", () => {
    expect(formatDuration(60_000)).toBe("1m");
    expect(formatDuration(120_000)).toBe("2m");
  });

  it("renders mixed minutes and seconds", () => {
    expect(formatDuration(381_000)).toBe("6m 21s");
  });

  it("renders mixed hours and minutes, hides zero seconds", () => {
    expect(formatDuration(3_600_000)).toBe("1h");
    expect(formatDuration(3_660_000)).toBe("1h 1m");
    expect(formatDuration(3_661_000)).toBe("1h 1m 1s");
  });

  it("carries rounding at the seconds → minutes boundary", () => {
    // 60_000 + 59_500 = 119_500 ms. Rounds to ``2m``, not ``1m 60s``.
    expect(formatDuration(119_500)).toBe("2m");
  });
});

describe("formatTokens", () => {
  it("returns plain number under 1000", () => {
    expect(formatTokens(999)).toBe("999");
  });

  it("uses one decimal in 1k–10k range", () => {
    expect(formatTokens(1500)).toBe("1.5k");
    expect(formatTokens(9999)).toBe("10.0k");
  });

  it("rounds to nearest k above 10k", () => {
    expect(formatTokens(15_500)).toBe("16k");
    expect(formatTokens(150_000)).toBe("150k");
  });
});

describe("pickVerb", () => {
  it("returns one of the canonical verbs", () => {
    for (let i = 0; i < 10; i++) {
      const v = pickVerb(i / 10);
      expect(SPINNER_VERBS).toContain(v);
    }
  });

  it("is deterministic given the same seed", () => {
    expect(pickVerb(0.5)).toBe(pickVerb(0.5));
  });

  it("covers different verbs across the seed range", () => {
    const seen = new Set<string>();
    for (let i = 0; i < 200; i++) {
      seen.add(pickVerb(Math.random()));
    }
    expect(seen.size).toBeGreaterThan(1);
  });
});
