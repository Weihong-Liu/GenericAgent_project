import { describe, expect, it } from "vitest";

import {
  emptyInput,
  locateCursor,
  reduceInput,
  splitLines,
} from "../state/inputBuffer.js";

const at = (value: string, cursor: number) => ({ value, cursor });

describe("inputBuffer.insert", () => {
  it("inserts text at the cursor", () => {
    const next = reduceInput(emptyInput, { type: "insert", text: "hi" });
    expect(next).toEqual({ value: "hi", cursor: 2 });
  });

  it("respects the cursor position in the middle of the buffer", () => {
    const next = reduceInput(at("ab", 1), { type: "insert", text: "X" });
    expect(next).toEqual({ value: "aXb", cursor: 2 });
  });
});

describe("inputBuffer.backspace / delete_forward", () => {
  it("backspace removes the char to the left of the cursor", () => {
    expect(reduceInput(at("abc", 2), { type: "backspace" })).toEqual({
      value: "ac",
      cursor: 1,
    });
  });

  it("delete_forward removes the char under the cursor", () => {
    expect(reduceInput(at("abc", 1), { type: "delete_forward" })).toEqual({
      value: "ac",
      cursor: 1,
    });
  });

  it("backspace at position 0 is a no-op", () => {
    expect(reduceInput(at("abc", 0), { type: "backspace" })).toEqual(at("abc", 0));
  });
});

describe("inputBuffer.kill_word_back", () => {
  it("removes the previous word", () => {
    expect(
      reduceInput(at("hello world", 11), { type: "kill_word_back" }),
    ).toEqual({ value: "hello ", cursor: 6 });
  });

  it("skips trailing whitespace before deleting the word", () => {
    expect(
      reduceInput(at("hello world   ", 14), { type: "kill_word_back" }),
    ).toEqual({ value: "hello ", cursor: 6 });
  });

  it("falls back to deleting one char when no word boundary is hit", () => {
    expect(
      reduceInput(at("...", 3), { type: "kill_word_back" }),
    ).toEqual({ value: "..", cursor: 2 });
  });
});

describe("inputBuffer.kill_to_line_start / line_end", () => {
  it("kills back to line start", () => {
    expect(
      reduceInput(at("aa\nbb cc", 7), { type: "kill_to_line_start" }),
    ).toEqual({ value: "aa\nc", cursor: 3 });
  });

  it("kills to line end", () => {
    expect(
      reduceInput(at("aa bb\ncc", 3), { type: "kill_to_line_end" }),
    ).toEqual({ value: "aa \ncc", cursor: 3 });
  });
});

describe("inputBuffer.move", () => {
  it("word_left jumps over whitespace then word", () => {
    const next = reduceInput(at("foo bar baz", 11), { type: "move", to: "word_left" });
    expect(next.cursor).toBe(8);
  });

  it("word_right jumps over whitespace then word", () => {
    const next = reduceInput(at("foo bar baz", 0), { type: "move", to: "word_right" });
    expect(next.cursor).toBe(3);
  });

  it("line_start / line_end work mid-line", () => {
    const startState = at("alpha\nbravo charlie", 12);
    expect(reduceInput(startState, { type: "move", to: "line_start" }).cursor).toBe(6);
    expect(reduceInput(startState, { type: "move", to: "line_end" }).cursor).toBe(19);
  });

  it("up / down preserve column when possible", () => {
    const startState = at("aaaa\nbb\ncccc", 2); // top row, col 2
    const after = reduceInput(startState, { type: "move", to: "down" });
    expect(after.cursor).toBe(7); // \nbb has length 2, col clamps to 2
  });

  it("up at first line is a no-op", () => {
    expect(reduceInput(at("abc", 1), { type: "move", to: "up" }).cursor).toBe(1);
  });
});

describe("inputBuffer.locateCursor", () => {
  it("locates row/col in a multiline buffer", () => {
    expect(locateCursor(at("aa\nbb\ncc", 5))).toEqual({ row: 1, col: 2 });
  });

  it("locates start-of-buffer", () => {
    expect(locateCursor(emptyInput)).toEqual({ row: 0, col: 0 });
  });
});

describe("splitLines", () => {
  it("returns one empty line for an empty buffer", () => {
    expect(splitLines("")).toEqual([""]);
  });

  it("splits on newlines", () => {
    expect(splitLines("a\nb\n")).toEqual(["a", "b", ""]);
  });
});
