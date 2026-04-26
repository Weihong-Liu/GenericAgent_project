import { describe, expect, it } from "vitest";

import {
  type VimAction,
  type VimState,
  newVimState,
  reduceVim,
} from "../state/vimReducer.js";

const fromString = (value: string, cursor = 0): VimState =>
  newVimState({ value, cursor });

const press = (key: string): VimAction => ({ type: "key", input: key });
const seq = (state: VimState, ...keys: string[]): VimState =>
  keys.reduce((s, k) => reduceVim(s, press(k)), state);

describe("vimReducer — mode switches", () => {
  it("starts in NORMAL mode", () => {
    expect(fromString("").mode).toBe("normal");
  });

  it("i enters INSERT mode at cursor", () => {
    const after = seq(fromString("hi", 0), "i");
    expect(after.mode).toBe("insert");
  });

  it("a enters INSERT mode after the cursor", () => {
    const after = seq(fromString("hi", 0), "a");
    expect(after.mode).toBe("insert");
    expect(after.buffer.cursor).toBe(1);
  });

  it("A jumps to line end and enters INSERT mode", () => {
    const after = seq(fromString("hello", 0), "A");
    expect(after.mode).toBe("insert");
    expect(after.buffer.cursor).toBe(5);
  });

  it("Esc (empty input) returns to NORMAL", () => {
    const after = seq(fromString("hi", 0), "i", "");
    expect(after.mode).toBe("normal");
  });

  it("v enters VISUAL mode and pins the anchor", () => {
    const after = seq(fromString("hello", 2), "v");
    expect(after.mode).toBe("visual");
    expect(after.visualAnchor).toBe(2);
  });
});

describe("vimReducer — INSERT", () => {
  it("inserts characters at cursor", () => {
    const after = reduceVim(seq(fromString("", 0), "i"), press("h"));
    expect(after.buffer.value).toBe("h");
  });
});

describe("vimReducer — motions", () => {
  it("h moves left", () => {
    const after = seq(fromString("abc", 2), "h");
    expect(after.buffer.cursor).toBe(1);
  });

  it("l moves right", () => {
    const after = seq(fromString("abc", 0), "l");
    expect(after.buffer.cursor).toBe(1);
  });

  it("w jumps to start of the next word (skipping trailing whitespace)", () => {
    const after = seq(fromString("foo bar baz", 0), "w");
    expect(after.buffer.cursor).toBe(4);
  });

  it("b jumps to previous word", () => {
    const after = seq(fromString("foo bar baz", 11), "b");
    expect(after.buffer.cursor).toBe(8);
  });

  it("0 moves to line start", () => {
    const after = seq(fromString("hello", 4), "0");
    expect(after.buffer.cursor).toBe(0);
  });

  it("$ moves to line end", () => {
    const after = seq(fromString("hello", 0), "$");
    expect(after.buffer.cursor).toBe(5);
  });

  it("G jumps to buffer end", () => {
    const after = seq(fromString("a\nbb\nccc", 0), "G");
    expect(after.buffer.cursor).toBe(8);
  });
});

describe("vimReducer — operators", () => {
  it("dw deletes the next word", () => {
    const after = seq(fromString("foo bar baz", 0), "d", "w");
    expect(after.buffer.value).toBe("bar baz");
    expect(after.buffer.cursor).toBe(0);
    expect(after.register).toBe("foo ");
  });

  it("dd deletes the current line", () => {
    const after = seq(fromString("alpha\nbravo\ncharlie", 0), "d", "d");
    expect(after.buffer.value).toBe("bravo\ncharlie");
  });

  it("yy yanks the current line into register", () => {
    const after = seq(fromString("alpha\nbravo", 0), "y", "y");
    expect(after.register).toBe("alpha\n");
    expect(after.buffer.value).toBe("alpha\nbravo");
  });

  it("cw deletes word and enters INSERT", () => {
    const after = seq(fromString("foo bar", 0), "c", "w");
    expect(after.mode).toBe("insert");
    expect(after.buffer.value).toBe("bar");
  });

  it("x deletes char under cursor", () => {
    const after = seq(fromString("hello", 1), "x");
    expect(after.buffer.value).toBe("hllo");
  });
});

describe("vimReducer — VISUAL operators", () => {
  it("d on a visual range deletes it", () => {
    // Select "ell" (cursor moves from 1 → 3 in VISUAL via two l's).
    const after = seq(fromString("hello", 1), "v", "l", "l", "d");
    // Range was cursor[1..3], inclusive end → 4, deleted "ell".
    expect(after.buffer.value).toBe("ho");
    expect(after.mode).toBe("normal");
  });
});

describe("vimReducer — undo", () => {
  it("u rewinds the last edit", () => {
    let state = fromString("hello", 0);
    state = seq(state, "x"); // delete h
    expect(state.buffer.value).toBe("ello");
    state = seq(state, "u");
    expect(state.buffer.value).toBe("hello");
  });
});
