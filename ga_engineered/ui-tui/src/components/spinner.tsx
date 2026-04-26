/**
 * Tiny presentational wrappers around ``useSpinner`` so the rest of the
 * UI can drop a spinner in without thinking about hook setup.
 */

import { Text } from "ink";
import React from "react";

import {
  type BrailleSpinnerName,
  useSpinner,
  useSpinnerState,
} from "../hooks/useSpinner.js";

interface SpinnerTextProps {
  name?: BrailleSpinnerName;
  color?: string;
  paused?: boolean;
}

export function SpinnerText({
  name = "cascade",
  color = "yellow",
  paused = false,
}: SpinnerTextProps): React.ReactElement {
  const frame = useSpinner(name, { paused });
  return <Text color={color}>{frame}</Text>;
}

/**
 * Blinking cursor used at the tail of a streaming assistant bubble.
 *
 * We drive the blink off the spinner's frame *index* (parity 0/1) rather
 * than off the frame's character length, so a future change to the
 * underlying spinner data cannot freeze the cursor on or off.
 */
export function StreamCursor({
  color = "gray",
}: {
  color?: string;
} = {}): React.ReactElement {
  const { index } = useSpinnerState("breathe", { interval: 200 });
  const visible = index % 2 === 0;
  return <Text color={color}>{visible ? "▍" : " "}</Text>;
}
