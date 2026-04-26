import { describe, expect, it } from "vitest";

import { activeMention, applyMention, detectMode } from "../state/modeDetector.js";

describe("detectMode", () => {
  it("recognises slash, bash, mention, chat", () => {
    expect(detectMode("/help")).toBe("slash");
    expect(detectMode("!ls")).toBe("bash");
    expect(detectMode("see @src/", 8)).toBe("mention");
    expect(detectMode("plain text")).toBe("chat");
  });

  it("falls back to chat when @ is followed by whitespace", () => {
    // mention is "active" only when there is NO whitespace between the
    // @ and the cursor — once a space appears, the mention is committed.
    expect(detectMode("see @src ")).toBe("chat");
  });

  it("treats / and ! prefixes as exclusive of mention", () => {
    expect(detectMode("/foo @bar")).toBe("slash");
    expect(detectMode("!cmd @bar")).toBe("bash");
  });
});

describe("activeMention", () => {
  it("returns null when there is no @ before the cursor", () => {
    expect(activeMention("hello world", 11)).toBeNull();
  });

  it("captures the partial query between @ and cursor", () => {
    const tok = activeMention("see @src/com", 12);
    expect(tok).not.toBeNull();
    expect(tok?.query).toBe("src/com");
    expect(tok?.start).toBe(4);
    expect(tok?.end).toBe(12);
  });

  it("ignores @ separated from the cursor by whitespace", () => {
    expect(activeMention("see @one and ", 13)).toBeNull();
  });

  it("works at the start of the buffer", () => {
    const tok = activeMention("@foo", 4);
    expect(tok?.query).toBe("foo");
    expect(tok?.start).toBe(0);
  });
});

describe("applyMention", () => {
  it("replaces the active mention with the picked path + space", () => {
    const result = applyMention("see @src/com", 12, "src/components/App.tsx");
    expect(result.value).toBe("see @src/components/App.tsx ");
    expect(result.cursor).toBe(result.value.length);
  });

  it("is a no-op when no active mention exists", () => {
    const result = applyMention("hello", 5, "ignored.ts");
    expect(result.value).toBe("hello");
    expect(result.cursor).toBe(5);
  });
});
