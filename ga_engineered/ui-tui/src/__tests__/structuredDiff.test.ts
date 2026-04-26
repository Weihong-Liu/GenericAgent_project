import { describe, expect, it } from "vitest";

import { classifyDiffLine, parseUnifiedDiff } from "../components/structuredDiff.js";
import { looksLikeUnifiedDiff } from "../components/fileEditToolDiff.js";

describe("structured diff parsing", () => {
  it("classifies unified diff lines", () => {
    expect(classifyDiffLine("diff --git a/x b/x")).toBe("header");
    expect(classifyDiffLine("@@ -1 +1 @@")).toBe("hunk");
    expect(classifyDiffLine("+added")).toBe("add");
    expect(classifyDiffLine("-removed")).toBe("remove");
    expect(classifyDiffLine(" context")).toBe("context");
  });

  it("parses each diff line in order", () => {
    const parsed = parseUnifiedDiff("diff --git a/x b/x\n@@ -1 +1 @@\n-old\n+new");
    expect(parsed.map((line) => line.kind)).toEqual(["header", "hunk", "remove", "add"]);
  });

  it("detects common unified diff shapes", () => {
    expect(looksLikeUnifiedDiff("@@ -1 +1 @@\n-old\n+new")).toBe(true);
    expect(looksLikeUnifiedDiff("--- a/x\n+++ b/x\n+new")).toBe(true);
    expect(looksLikeUnifiedDiff("plain text")).toBe(false);
  });
});
