import { describe, expect, it } from "vitest";

import {
  padVisual,
  visualWidth,
  wrapVisual,
} from "../markdown/visualWidth.js";

describe("visualWidth", () => {
  it("counts ASCII as one column per character", () => {
    expect(visualWidth("hello")).toBe(5);
  });

  it("counts CJK ideographs as two columns each", () => {
    expect(visualWidth("说明")).toBe(4);
    expect(visualWidth("名称")).toBe(4);
    expect(visualWidth("中文 abc")).toBe(8); // 2+2+1+1+1+1
  });

  it("counts emoji as two columns", () => {
    expect(visualWidth("✓")).toBeGreaterThanOrEqual(1);
    expect(visualWidth("🔥")).toBe(2);
  });

  it("treats zero-width joiners as 0", () => {
    expect(visualWidth("​")).toBe(0);
  });
});

describe("padVisual", () => {
  it("pads to the requested visual width with left alignment", () => {
    const padded = padVisual("ab", 6, "left");
    expect(padded).toBe("ab    ");
    expect(visualWidth(padded)).toBe(6);
  });

  it("pads CJK strings correctly", () => {
    // "说明" is 4 cols. Pad to width 8 → 4 spaces of right padding.
    const padded = padVisual("说明", 8, "left");
    expect(visualWidth(padded)).toBe(8);
    expect(padded).toBe("说明    ");
  });

  it("right-aligns when asked", () => {
    expect(padVisual("ab", 6, "right")).toBe("    ab");
  });

  it("centre-aligns when asked", () => {
    expect(padVisual("a", 5, "center")).toBe("  a  ");
  });

  it("returns the string unchanged when wider than ``width``", () => {
    expect(padVisual("hello world", 4, "left")).toBe("hello world");
  });
});

describe("wrapVisual", () => {
  it("returns one line when text fits in width", () => {
    expect(wrapVisual("hello world", 80)).toEqual(["hello world"]);
  });

  it("breaks at word boundaries when over width", () => {
    const out = wrapVisual("hello world how are you", 10);
    // Each line fits in width (trailing whitespace is OK), and the
    // non-whitespace content concatenates back to the original.
    expect(out.every((l) => visualWidth(l) <= 10)).toBe(true);
    expect(out.join(" ").replace(/\s+/g, " ").trim()).toBe(
      "hello world how are you",
    );
  });

  it("hard-breaks individual words that exceed width", () => {
    const out = wrapVisual("supercalifragilistic", 6);
    expect(out.every((l) => visualWidth(l) <= 6)).toBe(true);
    expect(out.join("")).toBe("supercalifragilistic");
  });

  it("respects visual width for CJK", () => {
    // "类型" "名称" "说明" each = 4 cols; with spaces = 14 cols total.
    // Wrapping at width 8 should split into 2 lines.
    const out = wrapVisual("类型 名称 说明", 8);
    expect(out.every((l) => visualWidth(l) <= 8)).toBe(true);
  });
});
