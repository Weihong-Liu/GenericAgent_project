/**
 * Multiline TextInput.
 *
 * Replaces the ``ink-text-input`` dependency. Owns its own buffer
 * state via the pure ``inputBuffer`` reducer; surfaces value changes to
 * the parent via ``onChange`` and submission via ``onSubmit``. Tab and
 * arrow events are not consumed when ``focus`` is false so the parent
 * (slash overlay, history search) can grab them.
 *
 * Free-code-style key bindings:
 *   - Enter submits, Shift-Enter / Alt-Enter inserts a newline.
 *   - Backspace deletes the char left of the cursor; Delete deletes right.
 *   - Ctrl-W kills the previous word; Ctrl-U kills back to line start;
 *     Ctrl-K kills to end of line.
 *   - Ctrl-A / Home jump to line start; Ctrl-E / End to line end.
 *   - Arrow keys move; Ctrl/Alt + Left/Right skip a word.
 *   - Up/Down move between visual lines; the parent can intercept the
 *     "off the top/bottom" case via ``onHistoryUp`` / ``onHistoryDown``.
 *   - Bracketed paste: while ``isPasting`` returns true, Enter inserts
 *     a newline instead of submitting.
 */

import { Box, Text, useInput } from "ink";
import React, { useCallback, useEffect } from "react";

import {
  InputState,
  emptyInput,
  locateCursor,
  reduceInput,
  splitLines,
} from "../state/inputBuffer.js";

export interface TextInputProps {
  value: string;
  onChange: (next: string) => void;
  onSubmit: (text: string) => void;
  /** When false the component does not consume any keys at all. */
  focus?: boolean;
  /**
   * When true, navigation keys (arrows, Tab) are not consumed by the
   * input — letting the parent route them to an overlay. Printable
   * keys still flow through, so the user can continue typing while
   * the overlay narrows the suggestion list. Default: false.
   */
  disableNavigation?: boolean;
  /** Optional placeholder shown when value is empty. */
  placeholder?: string;
  /** Glyph + colour for the leading prompt indicator. */
  prefix?: React.ReactNode;
  /** Up arrow at the top line of the buffer — return new value to apply. */
  onHistoryUp?: (current: string) => string | null;
  /** Down arrow at the bottom line — return new value to apply. */
  onHistoryDown?: (current: string) => string | null;
  /** Bracketed-paste detector (parent owns this so all overlays share it). */
  isPasting?: () => boolean;
  observePaste?: (chunk: string) => void;
  /** Called after a successful submit so parent can reset history index. */
  onAfterSubmit?: () => void;
}

export function TextInput({
  value,
  onChange,
  onSubmit,
  focus = true,
  disableNavigation = false,
  placeholder,
  prefix,
  onHistoryUp,
  onHistoryDown,
  isPasting,
  observePaste,
  onAfterSubmit,
}: TextInputProps): React.ReactElement {
  const [state, setState] = React.useState<InputState>({
    value,
    cursor: value.length,
  });

  // Sync external value into local state when it changes from the outside
  // (history recall, completion, slash command apply, etc.). Cursor lands
  // at end-of-buffer because that's where any external caller wants it.
  useEffect(() => {
    if (value !== state.value) {
      setState({ value, cursor: value.length });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  const apply = useCallback(
    (action: Parameters<typeof reduceInput>[1]) => {
      setState((prev) => {
        const next = reduceInput(prev, action);
        if (next.value !== prev.value) onChange(next.value);
        return next;
      });
    },
    [onChange],
  );

  useInput(
    (input, key) => {
      if (!focus) return;

      // Submit (Enter without modifier, but only outside a paste burst).
      if (key.return && !key.shift && !key.meta) {
        if (isPasting?.()) {
          apply({ type: "newline" });
          return;
        }
        const text = state.value;
        onSubmit(text);
        if (onAfterSubmit) onAfterSubmit();
        // Clear local buffer; parent typically clears value too.
        setState(emptyInput);
        return;
      }

      // Newline (Shift-Enter / Alt-Enter / pasted newline char).
      if (key.return && (key.shift || key.meta)) {
        apply({ type: "newline" });
        return;
      }

      // Editing keys.
      if (key.backspace || key.delete) {
        if (key.ctrl) apply({ type: "kill_word_back" });
        else apply({ type: "backspace" });
        return;
      }

      // Cursor movement.
      if (key.leftArrow) {
        apply({ type: "move", to: key.ctrl || key.meta ? "word_left" : "left" });
        return;
      }
      if (key.rightArrow) {
        apply({ type: "move", to: key.ctrl || key.meta ? "word_right" : "right" });
        return;
      }
      // ↑/↓ and Tab: skip when an overlay owns navigation. The parent
      // routes these keys to its own ``useInput`` to drive the overlay.
      if (disableNavigation && (key.upArrow || key.downArrow || key.tab)) {
        return;
      }
      if (key.upArrow) {
        const lines = splitLines(state.value);
        const { row } = locateCursor(state);
        if (row === 0 && onHistoryUp) {
          const next = onHistoryUp(state.value);
          if (next !== null) {
            setState({ value: next, cursor: next.length });
            onChange(next);
          }
          return;
        }
        if (lines.length > 1) apply({ type: "move", to: "up" });
        return;
      }
      if (key.downArrow) {
        const lines = splitLines(state.value);
        const { row } = locateCursor(state);
        if (row === lines.length - 1 && onHistoryDown) {
          const next = onHistoryDown(state.value);
          if (next !== null) {
            setState({ value: next, cursor: next.length });
            onChange(next);
          }
          return;
        }
        if (lines.length > 1) apply({ type: "move", to: "down" });
        return;
      }

      // Ctrl-A / Ctrl-E line-start / line-end. Ink doesn't expose Home/End
      // directly on every terminal, so we map both to ctrl shortcuts.
      if (key.ctrl && input === "a") {
        apply({ type: "move", to: "line_start" });
        return;
      }
      if (key.ctrl && input === "e") {
        apply({ type: "move", to: "line_end" });
        return;
      }
      if (key.ctrl && input === "u") {
        apply({ type: "kill_to_line_start" });
        return;
      }
      if (key.ctrl && input === "k") {
        apply({ type: "kill_to_line_end" });
        return;
      }
      if (key.ctrl && input === "w") {
        apply({ type: "kill_word_back" });
        return;
      }

      // Plain printable input. Tab characters are skipped when
      // ``disableNavigation`` is on (the parent's overlay handler
      // consumes Tab as completion). Without this guard, pressing Tab
      // with an open overlay would insert a literal "\t" into the
      // buffer.
      if (input && !key.ctrl && !key.meta && !(disableNavigation && key.tab)) {
        observePaste?.(input);
        apply({ type: "insert", text: input });
      }
    },
    { isActive: focus },
  );

  const lines = splitLines(state.value);
  const { row, col } = locateCursor(state);
  const showPlaceholder = state.value.length === 0 && placeholder !== undefined;

  return (
    <Box flexDirection="column">
      {showPlaceholder ? (
        <Text>
          {prefix ?? null}
          {/*
            * A block cursor at column 0 even when the buffer is empty —
            * otherwise the placeholder reads as a static hint with no
            * affordance that the prompt is focused. Matches free-code's
            * always-visible caret.
            */}
          {focus ? <Text inverse> </Text> : null}
          <Text color="gray" dimColor>
            {placeholder}
          </Text>
        </Text>
      ) : (
        lines.map((lineText, idx) => (
          <Text key={idx}>
            {idx === 0 ? prefix ?? null : <Text color="gray">  </Text>}
            {renderLine(lineText, idx === row && focus ? col : -1)}
          </Text>
        ))
      )}
    </Box>
  );
}

function renderLine(text: string, cursorCol: number): React.ReactElement {
  if (cursorCol < 0) {
    return <Text>{text}</Text>;
  }
  const before = text.slice(0, cursorCol);
  const at = text.slice(cursorCol, cursorCol + 1) || " ";
  const after = text.slice(cursorCol + 1);
  return (
    <Text>
      {before}
      <Text inverse>{at}</Text>
      {after}
    </Text>
  );
}
