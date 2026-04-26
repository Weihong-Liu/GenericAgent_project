/**
 * Frame-batching throttle for ``content_delta`` events.
 *
 * The transcript reducer is pure but Ink's diff is O(N) in the number
 * of children, so re-rendering on every single token from a fast LLM
 * (Claude can stream 100+ tokens/sec) starves the input loop. We
 * accumulate deltas in a ref and flush them on the next animation
 * frame (or a 16 ms timer when ``requestAnimationFrame`` isn't
 * available, e.g. in Node).
 *
 * The hook exposes a ``push(text)`` to record a delta and a
 * ``flush()`` that the parent calls when a turn ends, ensuring no
 * delta gets stuck in the buffer.
 */

import { useCallback, useEffect, useRef } from "react";

export interface UseStreamThrottleArgs {
  /** Called with the merged text whenever a frame fires. */
  onFlush: (mergedDelta: string) => void;
  /** Flush interval in ms — default 16 (≈60Hz). */
  intervalMs?: number;
}

export interface UseStreamThrottleApi {
  /** Append a delta; will be merged with any pending deltas. */
  push: (text: string) => void;
  /** Force a flush immediately (e.g. on turn_finished). */
  flush: () => void;
}

export function useStreamThrottle({
  onFlush,
  intervalMs = 16,
}: UseStreamThrottleArgs): UseStreamThrottleApi {
  const pending = useRef<string>("");
  const handle = useRef<NodeJS.Timeout | null>(null);
  const onFlushRef = useRef(onFlush);

  // Keep the callback up-to-date without re-arming the timer.
  useEffect(() => {
    onFlushRef.current = onFlush;
  }, [onFlush]);

  const flushNow = useCallback(() => {
    if (handle.current) {
      clearTimeout(handle.current);
      handle.current = null;
    }
    const text = pending.current;
    if (text.length === 0) return;
    pending.current = "";
    onFlushRef.current(text);
  }, []);

  const push = useCallback(
    (text: string) => {
      if (text.length === 0) return;
      pending.current += text;
      if (handle.current) return;
      handle.current = setTimeout(() => {
        handle.current = null;
        const merged = pending.current;
        if (merged.length === 0) return;
        pending.current = "";
        onFlushRef.current(merged);
      }, intervalMs);
    },
    [intervalMs],
  );

  // Flush on unmount so a half-streamed turn doesn't lose its tail.
  useEffect(() => {
    return () => {
      flushNow();
    };
  }, [flushNow]);

  return { push, flush: flushNow };
}
