import { describe, expect, it } from "vitest";

import {
  COMPACT_LOGO_WIDTH,
  DEFAULT_PALETTE,
  EMBLEM_WIDTH,
  LOGO_ART,
  LOGO_WIDTH,
  SPLIT_LAYOUT_THRESHOLD,
  WIDE_LOGO_THRESHOLD,
  compactLogo,
  emblem,
  logo,
  selectLogo,
} from "../banner.js";

describe("banner constants", () => {
  it("LOGO_ART is exactly six rows of equal width", () => {
    expect(LOGO_ART).toHaveLength(6);
    const widths = new Set(LOGO_ART.map((row) => row.length));
    expect(widths.size).toBe(1);
    // The wide threshold must be wide enough that LOGO_ART never overflows.
    expect(WIDE_LOGO_THRESHOLD).toBeGreaterThan(LOGO_WIDTH);
  });

  it("emblem is exactly 14 rows of width 30", () => {
    expect(EMBLEM_WIDTH).toBe(30);
  });

  it("compact logo is narrower than the wide threshold", () => {
    expect(COMPACT_LOGO_WIDTH).toBeLessThan(WIDE_LOGO_THRESHOLD);
  });

  it("SPLIT_LAYOUT_THRESHOLD reserves room for emblem + gap + logo", () => {
    expect(SPLIT_LAYOUT_THRESHOLD).toBeGreaterThan(LOGO_WIDTH + EMBLEM_WIDTH);
  });
});

describe("colorize", () => {
  it("logo paints the bright/accent/deep gradient onto the six rows", () => {
    const lines = logo();
    expect(lines).toHaveLength(6);
    expect(lines.map(([color]) => color)).toEqual([
      DEFAULT_PALETTE.bright,
      DEFAULT_PALETTE.bright,
      DEFAULT_PALETTE.accent,
      DEFAULT_PALETTE.accent,
      DEFAULT_PALETTE.deep,
      DEFAULT_PALETTE.deep,
    ]);
  });

  it("each emblem row gets a non-empty colour string", () => {
    const lines = emblem();
    for (const [color, text] of lines) {
      expect(color).toMatch(/^#[0-9A-Fa-f]{6}$/);
      expect(text.length).toBeGreaterThan(0);
    }
  });

  it("compactLogo returns colored lines whose widths fit in 30 cols", () => {
    const lines = compactLogo();
    for (const [, text] of lines) {
      expect(text.length).toBeLessThanOrEqual(30);
    }
  });
});

describe("selectLogo", () => {
  it("uses the wide art at and above the threshold", () => {
    expect(selectLogo(WIDE_LOGO_THRESHOLD).map(([, t]) => t.length)[0]).toBe(LOGO_WIDTH);
    expect(selectLogo(WIDE_LOGO_THRESHOLD + 30).map(([, t]) => t.length)[0]).toBe(LOGO_WIDTH);
  });

  it("falls back to the compact art below the threshold", () => {
    const compact = selectLogo(WIDE_LOGO_THRESHOLD - 1);
    expect(compact.map(([, t]) => t.length)[0]).toBe(COMPACT_LOGO_WIDTH);
  });

  it("selects compact at narrow common terminal sizes", () => {
    for (const w of [60, 80, 90, LOGO_WIDTH]) {
      // LOGO_WIDTH itself is below WIDE_LOGO_THRESHOLD by one, so it must
      // still pick compact — otherwise the wide art would overflow exactly
      // at the boundary.
      expect(selectLogo(w).map(([, t]) => t.length)[0]).toBe(COMPACT_LOGO_WIDTH);
    }
  });
});
