/**
 * Pure Vim-mode reducer.
 *
 * Owns the input buffer + cursor + mode + a small undo stack. Modes:
 *   - INSERT  — forwards keystrokes verbatim into the buffer.
 *   - NORMAL  — interprets keys as motions / operators.
 *   - VISUAL  — keeps a selection anchor; operators apply to selection.
 *   - OPERATOR-PENDING — after ``d``/``c``/``y`` waits for a motion.
 *
 * Motions implemented: hjkl, w/b/e, 0/$/^, gg/G.
 * Operators: d, c, y; ``dd``/``cc``/``yy`` operate on the whole line.
 * ``x`` deletes the char under the cursor; ``u`` undoes the last edit;
 * ``i/I/a/A/o/O/v/V`` switch modes.
 *
 * The reducer is intentionally a pure function — the React hook in
 * ``../hooks/useVimInput.ts`` translates Ink key events into action
 * objects and dispatches them.
 */

import {
  InputState,
  reduceInput,
  splitLines,
} from "./inputBuffer.js";

export type VimMode = "insert" | "normal" | "visual" | "operator";

export interface VimState {
  buffer: InputState;
  mode: VimMode;
  /** Pending operator (``d``/``c``/``y``) waiting on a motion. */
  pendingOperator: "d" | "c" | "y" | null;
  /** Selection anchor in VISUAL mode. */
  visualAnchor: number | null;
  /** Yank register — the most recent text put on the register. */
  register: string;
  /** Bounded undo stack of (buffer + cursor) snapshots. */
  history: InputState[];
}

export type VimAction =
  | { type: "key"; input: string; ctrl?: boolean }
  | { type: "enter_insert" }
  | { type: "enter_normal" }
  | { type: "set_buffer"; value: string; cursor?: number };

const HISTORY_LIMIT = 100;

export function newVimState(buffer: InputState): VimState {
  return {
    buffer,
    mode: "normal",
    pendingOperator: null,
    visualAnchor: null,
    register: "",
    history: [],
  };
}

export function reduceVim(state: VimState, action: VimAction): VimState {
  if (action.type === "set_buffer") {
    return {
      ...state,
      buffer: { value: action.value, cursor: action.cursor ?? 0 },
    };
  }
  if (action.type === "enter_insert") {
    return pushUndo({ ...state, mode: "insert", pendingOperator: null });
  }
  if (action.type === "enter_normal") {
    return { ...state, mode: "normal", pendingOperator: null, visualAnchor: null };
  }

  // Mode-dispatch on key.
  switch (state.mode) {
    case "insert":
      return reduceInsertKey(state, action);
    case "normal":
      return reduceNormalKey(state, action);
    case "visual":
      return reduceVisualKey(state, action);
    case "operator":
      return reduceOperatorKey(state, action);
  }
}

// ---------------------------------------------------------------------------
// INSERT
// ---------------------------------------------------------------------------

function reduceInsertKey(
  state: VimState,
  action: Extract<VimAction, { type: "key" }>,
): VimState {
  const key = action.input;
  if (key === "") {
    // Esc → NORMAL
    return { ...state, mode: "normal" };
  }
  if (key.length === 0) return state;
  return {
    ...state,
    buffer: reduceInput(state.buffer, { type: "insert", text: key }),
  };
}

// ---------------------------------------------------------------------------
// NORMAL
// ---------------------------------------------------------------------------

function reduceNormalKey(
  state: VimState,
  action: Extract<VimAction, { type: "key" }>,
): VimState {
  const key = action.input;

  // Mode switches
  switch (key) {
    case "i":
      return pushUndo({ ...state, mode: "insert" });
    case "I":
      return pushUndo({
        ...state,
        mode: "insert",
        buffer: reduceInput(state.buffer, { type: "move", to: "line_start" }),
      });
    case "a":
      return pushUndo({
        ...state,
        mode: "insert",
        buffer: reduceInput(state.buffer, { type: "move", to: "right" }),
      });
    case "A":
      return pushUndo({
        ...state,
        mode: "insert",
        buffer: reduceInput(state.buffer, { type: "move", to: "line_end" }),
      });
    case "o": {
      const moved = reduceInput(state.buffer, { type: "move", to: "line_end" });
      return pushUndo({
        ...state,
        mode: "insert",
        buffer: reduceInput(moved, { type: "newline" }),
      });
    }
    case "O": {
      const moved = reduceInput(state.buffer, { type: "move", to: "line_start" });
      const inserted = reduceInput(moved, { type: "newline" });
      return pushUndo({
        ...state,
        mode: "insert",
        buffer: reduceInput(inserted, { type: "move", to: "up" }),
      });
    }
    case "v":
      return { ...state, mode: "visual", visualAnchor: state.buffer.cursor };
    case "u": {
      const previous = state.history[state.history.length - 1];
      if (!previous) return state;
      return {
        ...state,
        buffer: previous,
        history: state.history.slice(0, -1),
      };
    }
    case "x": {
      // Push the pre-edit buffer so ``u`` can rewind to it.
      const recorded = pushUndo(state);
      return {
        ...recorded,
        buffer: reduceInput(state.buffer, { type: "delete_forward" }),
      };
    }
  }

  // Operator pending — capture and wait for motion.
  if (key === "d" || key === "c" || key === "y") {
    return { ...state, mode: "operator", pendingOperator: key };
  }

  // Motions
  const moved = applyMotion(state.buffer, key);
  if (moved !== state.buffer) return { ...state, buffer: moved };
  return state;
}

// ---------------------------------------------------------------------------
// VISUAL
// ---------------------------------------------------------------------------

function reduceVisualKey(
  state: VimState,
  action: Extract<VimAction, { type: "key" }>,
): VimState {
  const key = action.input;
  if (key === "" || key === "v") {
    return { ...state, mode: "normal", visualAnchor: null };
  }
  if (key === "d" || key === "c" || key === "y") {
    return applyOperatorToSelection(state, key);
  }
  // Motions update the cursor; the anchor stays put.
  const moved = applyMotion(state.buffer, key);
  if (moved !== state.buffer) return { ...state, buffer: moved };
  return state;
}

// ---------------------------------------------------------------------------
// OPERATOR-PENDING
// ---------------------------------------------------------------------------

function reduceOperatorKey(
  state: VimState,
  action: Extract<VimAction, { type: "key" }>,
): VimState {
  const key = action.input;
  if (key === "") {
    return { ...state, mode: "normal", pendingOperator: null };
  }
  // Doubled operator (dd, cc, yy) → whole line.
  if (state.pendingOperator === key) {
    return applyOperatorToLine(state);
  }
  // Otherwise: operator + motion.
  const moved = applyMotion(state.buffer, key);
  if (moved === state.buffer) {
    // Unrecognized motion — drop the operator silently.
    return { ...state, mode: "normal", pendingOperator: null };
  }
  const start = Math.min(state.buffer.cursor, moved.cursor);
  const end = Math.max(state.buffer.cursor, moved.cursor);
  return finishOperatorRange(state, start, end);
}

// ---------------------------------------------------------------------------
// Motions
// ---------------------------------------------------------------------------

function applyMotion(buffer: InputState, key: string): InputState {
  switch (key) {
    case "h":
      return reduceInput(buffer, { type: "move", to: "left" });
    case "l":
      return reduceInput(buffer, { type: "move", to: "right" });
    case "j":
      return reduceInput(buffer, { type: "move", to: "down" });
    case "k":
      return reduceInput(buffer, { type: "move", to: "up" });
    case "w": {
      // Vim's ``w`` lands on the start of the next word, which means
      // skipping the trailing whitespace after the current word too —
      // important for ``dw`` to delete "foo " not just "foo".
      const moved = reduceInput(buffer, { type: "move", to: "word_right" });
      let cursor = moved.cursor;
      while (
        cursor < moved.value.length &&
        /\s/.test(moved.value[cursor] ?? "")
      ) {
        cursor += 1;
      }
      return { value: moved.value, cursor };
    }
    case "b":
      return reduceInput(buffer, { type: "move", to: "word_left" });
    case "0":
    case "^":
      return reduceInput(buffer, { type: "move", to: "line_start" });
    case "$":
      return reduceInput(buffer, { type: "move", to: "line_end" });
    case "G":
      return reduceInput(buffer, { type: "move", to: "buffer_end" });
    case "g":
      // ``gg`` requires a follow-up; for a single ``g`` keypress we
      // treat it the same as ``gg`` (move to buffer start) since vim
      // users rarely press a lone ``g``. A more faithful clone would
      // wait one key, but this MVP keeps the state machine simple.
      return reduceInput(buffer, { type: "move", to: "buffer_start" });
  }
  return buffer;
}

// ---------------------------------------------------------------------------
// Operators
// ---------------------------------------------------------------------------

function applyOperatorToLine(state: VimState): VimState {
  const lines = splitLines(state.buffer.value);
  const cursor = state.buffer.cursor;
  let consumed = 0;
  for (const line of lines) {
    const lineEnd = consumed + line.length;
    if (cursor <= lineEnd) {
      const start = consumed;
      const end = Math.min(state.buffer.value.length, lineEnd + 1);
      return finishOperatorRange(state, start, end);
    }
    consumed = lineEnd + 1;
  }
  return { ...state, mode: "normal", pendingOperator: null };
}

function applyOperatorToSelection(state: VimState, op: "d" | "c" | "y"): VimState {
  if (state.visualAnchor === null) return state;
  const start = Math.min(state.visualAnchor, state.buffer.cursor);
  const end = Math.max(state.visualAnchor, state.buffer.cursor) + 1;
  return finishOperatorRange({ ...state, pendingOperator: op }, start, end);
}

function finishOperatorRange(
  state: VimState,
  start: number,
  end: number,
): VimState {
  const text = state.buffer.value.slice(start, end);
  const op = state.pendingOperator;
  if (op === "y") {
    return {
      ...state,
      mode: "normal",
      pendingOperator: null,
      visualAnchor: null,
      register: text,
    };
  }
  const next = pushUndo(state);
  const newValue =
    state.buffer.value.slice(0, start) + state.buffer.value.slice(end);
  const buffer = { value: newValue, cursor: start };
  return {
    ...next,
    mode: op === "c" ? "insert" : "normal",
    pendingOperator: null,
    visualAnchor: null,
    register: text,
    buffer,
  };
}

// ---------------------------------------------------------------------------
// Undo
// ---------------------------------------------------------------------------

function pushUndo(state: VimState): VimState {
  const next = [...state.history, state.buffer];
  while (next.length > HISTORY_LIMIT) next.shift();
  return { ...state, history: next };
}
