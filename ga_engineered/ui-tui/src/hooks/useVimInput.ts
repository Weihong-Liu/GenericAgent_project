/**
 * Vim-mode input hook.
 *
 * Wraps Ink's ``useInput`` and routes keystrokes into the pure
 * :func:`reduceVim` state machine. The hook owns its state and exposes
 * the current value + cursor + mode label so the parent component can
 * render exactly the same UI shape as the regular TextInput.
 */

import { useInput } from "ink";
import { useCallback, useRef, useState } from "react";

import { type InputState } from "../state/inputBuffer.js";
import {
  type VimMode,
  type VimState,
  newVimState,
  reduceVim,
} from "../state/vimReducer.js";

export interface UseVimInputArgs {
  /** Initial buffer (e.g. when external code applies a draft). */
  value: string;
  /** Notify parent on value change. */
  onChange: (value: string) => void;
  /** Submit handler — called on Enter while in NORMAL mode. */
  onSubmit: (value: string) => void;
  focus?: boolean;
}

export interface UseVimInputApi {
  state: InputState;
  mode: VimMode;
  syncFromExternal: (value: string) => void;
}

export function useVimInput({
  value,
  onChange,
  onSubmit,
  focus = true,
}: UseVimInputArgs): UseVimInputApi {
  const [vim, setVim] = useState<VimState>(() =>
    newVimState({ value, cursor: value.length }),
  );
  const lastValue = useRef(value);

  // Keep an external sync hook so the parent can apply history/completion
  // results without fighting the reducer. We don't trigger this from the
  // value-prop sync path because that would create a loop.
  const syncFromExternal = useCallback((next: string) => {
    setVim((prev) =>
      reduceVim(prev, { type: "set_buffer", value: next, cursor: next.length }),
    );
    lastValue.current = next;
  }, []);

  useInput(
    (input, key) => {
      if (!focus) return;

      // Esc → NORMAL via empty input convention.
      if (key.escape) {
        setVim((prev) => reduceVim(prev, { type: "key", input: "" }));
        return;
      }

      // In NORMAL mode, plain Enter submits.
      if (key.return) {
        if (vim.mode === "normal") {
          onSubmit(vim.buffer.value);
          // Reset buffer post-submit.
          setVim(newVimState({ value: "", cursor: 0 }));
          lastValue.current = "";
          onChange("");
          return;
        }
        // INSERT mode Enter inserts a newline.
        setVim((prev) => reduceVim(prev, { type: "key", input: "\n" }));
        return;
      }

      // Backspace in INSERT mode is a builtin "delete left of cursor".
      if (key.backspace || key.delete) {
        if (vim.mode === "insert") {
          setVim((prev) => ({
            ...prev,
            buffer: reduceBuf(prev.buffer, "backspace"),
          }));
        }
        return;
      }

      // Plain printable char → reducer.
      const stroke = input;
      if (stroke.length > 0) {
        setVim((prev) => {
          const next = reduceVim(prev, { type: "key", input: stroke });
          if (next.buffer.value !== prev.buffer.value) {
            // Defer onChange to a microtask so React doesn't recurse.
            queueMicrotask(() => onChange(next.buffer.value));
            lastValue.current = next.buffer.value;
          }
          return next;
        });
      }
    },
    { isActive: focus },
  );

  return {
    state: vim.buffer,
    mode: vim.mode,
    syncFromExternal,
  };
}

function reduceBuf(buffer: InputState, action: "backspace"): InputState {
  if (action === "backspace") {
    if (buffer.cursor === 0) return buffer;
    return {
      value:
        buffer.value.slice(0, buffer.cursor - 1) + buffer.value.slice(buffer.cursor),
      cursor: buffer.cursor - 1,
    };
  }
  return buffer;
}
