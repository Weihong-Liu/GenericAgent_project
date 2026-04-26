/**
 * Vim-mode TextInput.
 *
 * A drop-in alternative to :func:`TextInput` that delegates editing to
 * the pure ``vimReducer`` via ``useVimInput``. Same prop shape; the
 * parent decides which to render based on the user's preference.
 */

import { Box, Text } from "ink";
import React from "react";

import { useVimInput, type UseVimInputApi } from "../hooks/useVimInput.js";
import {
  locateCursor,
  splitLines,
  type InputState,
} from "../state/inputBuffer.js";
import type { VimMode } from "../state/vimReducer.js";

export interface VimTextInputProps {
  value: string;
  onChange: (next: string) => void;
  onSubmit: (text: string) => void;
  focus?: boolean;
  placeholder?: string;
  prefix?: React.ReactNode;
  /**
   * The mode label is exposed via this callback so a parent (e.g. the
   * status bar) can render a "VIM NORMAL" pill without subscribing to
   * the hook itself.
   */
  onModeChange?: (mode: VimMode) => void;
}

export function VimTextInput({
  value,
  onChange,
  onSubmit,
  focus = true,
  placeholder,
  prefix,
  onModeChange,
}: VimTextInputProps): React.ReactElement {
  const api = useVimInput({ value, onChange, onSubmit, focus });
  React.useEffect(() => {
    onModeChange?.(api.mode);
  }, [api.mode, onModeChange]);

  return <RenderBuffer api={api} placeholder={placeholder} prefix={prefix} focus={focus} />;
}

function RenderBuffer({
  api,
  placeholder,
  prefix,
  focus,
}: {
  api: UseVimInputApi;
  placeholder: string | undefined;
  prefix: React.ReactNode;
  focus: boolean;
}): React.ReactElement {
  const state: InputState = api.state;
  const lines = splitLines(state.value);
  const { row, col } = locateCursor(state);
  const showPlaceholder = state.value.length === 0 && placeholder !== undefined;

  return (
    <Box flexDirection="column">
      {showPlaceholder ? (
        <Text>
          {prefix ?? null}
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
  if (cursorCol < 0) return <Text>{text}</Text>;
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
