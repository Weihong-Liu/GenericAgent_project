/**
 * Pure text-buffer model for the multiline input box.
 *
 * Tracks the editable string plus a single cursor offset (in *code points*,
 * not bytes). All editing operations are pure: ``apply(state, action)``
 * returns a new state, never mutates. That keeps the state machine
 * trivial to unit-test outside React.
 *
 * Free-code uses a similar split between buffer + cursor + viewport;
 * here we only model buffer + cursor and let the renderer derive
 * line-wrapping on the fly from the terminal width.
 */

export interface InputState {
  /** Full editable text (may contain newlines for multiline). */
  value: string;
  /** Cursor position as a string offset (0..value.length, inclusive). */
  cursor: number;
}

export const emptyInput: InputState = { value: "", cursor: 0 };

export type InputAction =
  | { type: "set"; value: string; cursor?: number }
  | { type: "insert"; text: string }
  | { type: "newline" }
  | { type: "backspace" }
  | { type: "delete_forward" }
  | { type: "kill_word_back" }
  | { type: "kill_to_line_start" }
  | { type: "kill_to_line_end" }
  | { type: "move"; to: CursorMove };

export type CursorMove =
  | "left"
  | "right"
  | "up"
  | "down"
  | "word_left"
  | "word_right"
  | "line_start"
  | "line_end"
  | "buffer_start"
  | "buffer_end";

export function reduceInput(state: InputState, action: InputAction): InputState {
  switch (action.type) {
    case "set":
      return clampCursor({
        value: action.value,
        cursor: action.cursor ?? state.cursor,
      });

    case "insert":
      if (action.text.length === 0) return state;
      return {
        value: state.value.slice(0, state.cursor) + action.text + state.value.slice(state.cursor),
        cursor: state.cursor + action.text.length,
      };

    case "newline":
      return reduceInput(state, { type: "insert", text: "\n" });

    case "backspace":
      if (state.cursor === 0) return state;
      return {
        value: state.value.slice(0, state.cursor - 1) + state.value.slice(state.cursor),
        cursor: state.cursor - 1,
      };

    case "delete_forward":
      if (state.cursor >= state.value.length) return state;
      return {
        value: state.value.slice(0, state.cursor) + state.value.slice(state.cursor + 1),
        cursor: state.cursor,
      };

    case "kill_word_back": {
      const wordStart = previousWordBoundary(state.value, state.cursor);
      if (wordStart === state.cursor) return state;
      return {
        value: state.value.slice(0, wordStart) + state.value.slice(state.cursor),
        cursor: wordStart,
      };
    }

    case "kill_to_line_start": {
      const lineStart = currentLineStart(state.value, state.cursor);
      if (lineStart === state.cursor) return state;
      return {
        value: state.value.slice(0, lineStart) + state.value.slice(state.cursor),
        cursor: lineStart,
      };
    }

    case "kill_to_line_end": {
      const lineEnd = currentLineEnd(state.value, state.cursor);
      if (lineEnd === state.cursor) return state;
      return {
        value: state.value.slice(0, state.cursor) + state.value.slice(lineEnd),
        cursor: state.cursor,
      };
    }

    case "move":
      return clampCursor({ value: state.value, cursor: moveCursor(state, action.to) });
  }
}

// ---------------------------------------------------------------------------
// Cursor helpers
// ---------------------------------------------------------------------------

function clampCursor(state: InputState): InputState {
  if (state.cursor < 0) return { ...state, cursor: 0 };
  if (state.cursor > state.value.length) return { ...state, cursor: state.value.length };
  return state;
}

function moveCursor(state: InputState, to: CursorMove): number {
  switch (to) {
    case "left":
      return Math.max(0, state.cursor - 1);
    case "right":
      return Math.min(state.value.length, state.cursor + 1);
    case "word_left":
      return previousWordBoundary(state.value, state.cursor);
    case "word_right":
      return nextWordBoundary(state.value, state.cursor);
    case "line_start":
      return currentLineStart(state.value, state.cursor);
    case "line_end":
      return currentLineEnd(state.value, state.cursor);
    case "buffer_start":
      return 0;
    case "buffer_end":
      return state.value.length;
    case "up":
      return moveVertical(state, -1);
    case "down":
      return moveVertical(state, 1);
  }
}

function moveVertical(state: InputState, delta: number): number {
  const lines = splitLines(state.value);
  const { row, col } = locate(lines, state.cursor);
  const targetRow = row + delta;
  if (targetRow < 0 || targetRow >= lines.length) return state.cursor;
  const targetLine = lines[targetRow] ?? "";
  const targetCol = Math.min(col, targetLine.length);
  return offsetOf(lines, targetRow, targetCol);
}

const WORD_RE = /[A-Za-z0-9_]/;

function previousWordBoundary(value: string, cursor: number): number {
  let i = cursor;
  // Skip whitespace immediately to the left.
  while (i > 0 && /\s/.test(value[i - 1] ?? "")) i--;
  // Skip the word itself.
  while (i > 0 && WORD_RE.test(value[i - 1] ?? "")) i--;
  // If we didn't move past a word at all, fall back to skipping one
  // non-word non-space character so Ctrl-W always makes progress.
  if (i === cursor && cursor > 0) i = cursor - 1;
  return i;
}

function nextWordBoundary(value: string, cursor: number): number {
  let i = cursor;
  while (i < value.length && /\s/.test(value[i] ?? "")) i++;
  while (i < value.length && WORD_RE.test(value[i] ?? "")) i++;
  if (i === cursor && cursor < value.length) i = cursor + 1;
  return i;
}

function currentLineStart(value: string, cursor: number): number {
  let i = cursor;
  while (i > 0 && value[i - 1] !== "\n") i--;
  return i;
}

function currentLineEnd(value: string, cursor: number): number {
  let i = cursor;
  while (i < value.length && value[i] !== "\n") i++;
  return i;
}

// ---------------------------------------------------------------------------
// Line splitting (used by the renderer too)
// ---------------------------------------------------------------------------

export function splitLines(value: string): string[] {
  if (value.length === 0) return [""];
  const lines = value.split("\n");
  return lines;
}

interface CursorPos {
  row: number;
  col: number;
}

function locate(lines: string[], offset: number): CursorPos {
  let consumed = 0;
  for (let row = 0; row < lines.length; row++) {
    const line = lines[row] ?? "";
    if (offset <= consumed + line.length) {
      return { row, col: offset - consumed };
    }
    consumed += line.length + 1; // +1 for the newline character
  }
  return { row: lines.length - 1, col: lines[lines.length - 1]?.length ?? 0 };
}

function offsetOf(lines: string[], row: number, col: number): number {
  let off = 0;
  for (let i = 0; i < row; i++) off += (lines[i]?.length ?? 0) + 1;
  return off + col;
}

export function locateCursor(state: InputState): CursorPos {
  return locate(splitLines(state.value), state.cursor);
}
