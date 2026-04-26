import { describe, expect, it } from "vitest";

import {
  extractToolArgument,
  formatCollapsedPreview,
  summariseToolResult,
} from "../toolSummary.js";

describe("summariseToolResult", () => {
  it("summarises web_scan content by scanned payload size, not JSON line count", () => {
    const raw = JSON.stringify({
      status: "success",
      metadata: { tabs_count: 2, active_tab: "tab-1" },
      content: "<html><body>ok</body></html>",
    });

    expect(summariseToolResult("web_scan", raw)).toBe("Scanned page (28 chars, 2 tabs)");
  });

  it("summarises tabs-only web_scan as a tab listing", () => {
    const raw = JSON.stringify({
      status: "success",
      metadata: { tabs_count: 1, active_tab: "tab-1" },
    });

    expect(summariseToolResult("web_scan", raw)).toBe("Listed 1 browser tab");
  });

  it("keeps error summaries explicit", () => {
    expect(summariseToolResult("web_scan", '{"error":"bridge down"}', true)).toBe(
      "Errored (23 chars, 1 lines)",
    );
  });

  it("extracts structured tool arguments for free-code-style tool headers", () => {
    expect(extractToolArgument('{"command":"git status 2>&1 | head -20"}', "command")).toBe(
      "git status 2>&1 | head -20",
    );
  });

  it("formats collapsed previews with hidden line counts", () => {
    expect(formatCollapsedPreview("a\nb\nc\nd\ne\n", 3)).toEqual({
      lines: ["a", "b", "c"],
      hiddenLines: 2,
    });
  });
});
