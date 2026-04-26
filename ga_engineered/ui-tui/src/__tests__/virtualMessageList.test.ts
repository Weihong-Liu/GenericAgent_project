import { describe, expect, it } from "vitest";

import { computeMessageWindow } from "../components/virtualMessageList.js";

describe("computeMessageWindow", () => {
  it("shows everything when the transcript fits", () => {
    expect(computeMessageWindow(3, 8)).toEqual({
      start: 0,
      end: 3,
      hiddenBefore: 0,
      hiddenAfter: 0,
    });
  });

  it("defaults to the tail of a long transcript", () => {
    expect(computeMessageWindow(20, 5)).toEqual({
      start: 15,
      end: 20,
      hiddenBefore: 15,
      hiddenAfter: 0,
    });
  });

  it("keeps a selected middle item visible", () => {
    expect(computeMessageWindow(20, 5, 8)).toEqual({
      start: 6,
      end: 11,
      hiddenBefore: 6,
      hiddenAfter: 9,
    });
  });

  it("clamps selected indexes at transcript edges", () => {
    expect(computeMessageWindow(20, 5, -10).start).toBe(0);
    expect(computeMessageWindow(20, 5, 99).end).toBe(20);
  });

  it("show-all mode disables windowing", () => {
    expect(computeMessageWindow(20, 5, null, true)).toEqual({
      start: 0,
      end: 20,
      hiddenBefore: 0,
      hiddenAfter: 0,
    });
  });
});
