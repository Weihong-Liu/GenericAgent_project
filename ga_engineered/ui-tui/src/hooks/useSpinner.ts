/**
 * Animated braille spinner hook.
 *
 * Wraps ``unicode-animations``' frame data in a React tick driven by
 * ``setInterval``. Component is responsible for unmounting (the hook
 * tears down its own timer in cleanup).
 */

import spinners, { type BrailleSpinnerName, type Spinner } from "unicode-animations";
import { useEffect, useState } from "react";

export type { BrailleSpinnerName };

export interface UseSpinnerOptions {
  /** Override the frame interval in ms. Defaults to the spinner's own. */
  interval?: number;
  /** Pause the animation. Useful when a tool finishes mid-render. */
  paused?: boolean;
}

const DEFAULT_NAME: BrailleSpinnerName = "cascade";

export interface SpinnerState {
  /** Current frame text (already a braille / unicode string). */
  frame: string;
  /** Zero-based index into the spinner's ``frames`` array. */
  index: number;
}

export function useSpinnerState(
  name: BrailleSpinnerName = DEFAULT_NAME,
  options: UseSpinnerOptions = {},
): SpinnerState {
  const spinner: Spinner = spinners[name] ?? spinners[DEFAULT_NAME];
  const interval = options.interval ?? spinner.interval ?? 80;
  const [frameIndex, setFrameIndex] = useState(0);
  const total = spinner.frames.length;

  useEffect(() => {
    if (options.paused || total === 0) return;
    const handle = setInterval(() => {
      setFrameIndex((idx) => (idx + 1) % total);
    }, interval);
    return () => clearInterval(handle);
  }, [interval, options.paused, total]);

  return {
    frame: spinner.frames[frameIndex] ?? "",
    index: frameIndex,
  };
}

/** Convenience wrapper that returns just the frame text. */
export function useSpinner(
  name: BrailleSpinnerName = DEFAULT_NAME,
  options: UseSpinnerOptions = {},
): string {
  return useSpinnerState(name, options).frame;
}
