/**
 * Free-code-style thinking spinner.
 *
 *   ✶ Waddling… (6m 21s · ↓ 15.5k tokens · thought for 29s)
 *
 * Pattern reference: free-code's SpinnerAnimationRow.tsx.
 *  - Verb picked ONCE per mount via ``useState`` initialiser, sampled
 *    from a 50-verb pool. New turn → new mount → new verb.
 *  - One 50 ms tick drives every dynamic field: spinner glyph, elapsed
 *    timer, smoothed token counter.
 *  - Spinner frames sweep forward then reverse (matches the visible
 *    "back-and-forth" pulse free-code's default characters do).
 *  - Token counter animates upward toward the target (``targetTokens``)
 *    with the same step rules free-code uses: +3 when behind by <70,
 *    +ceil(gap*0.15) when behind 70..200, +50 otherwise.
 *  - "thought for Ns" snapshot is taken once ``thoughtForMs`` becomes
 *    positive and freezes; while 0 we render "thinking…".
 */

import { Text } from "ink";
import React, { useEffect, useRef, useState } from "react";

import { pickVerb } from "../spinnerVerbs.js";
import { THEME } from "../theme.js";

const FRAMES_FORWARD = ["✻", "✸", "✷", "✶"] as const;
const FRAMES = [...FRAMES_FORWARD, ...[...FRAMES_FORWARD].reverse()];
const FRAME_INTERVAL_MS = 120;
const TICK_INTERVAL_MS = 50;

export interface ThinkingProps {
  /** Override the random verb (mainly for tests). */
  verb?: string;
  /** Wall-clock when the turn started, ms. */
  startedAt: number;
  /**
   * Target token count derived from streamed assistant chars (length /
   * 4). The displayed counter animates UPWARD toward this number;
   * passing 0 keeps it at 0.
   */
  targetTokens?: number;
  /**
   * If set, the model has finished thinking. Renders ``thought for
   * Ns`` instead of ``thinking…``. Frozen by the parent (don't tick
   * once set).
   */
  thoughtForMs?: number;
}

export function ThinkingIndicator({
  verb,
  startedAt,
  targetTokens = 0,
  thoughtForMs = 0,
}: ThinkingProps): React.ReactElement {
  // One-time random verb pick; ``useState(initialiser)`` only runs the
  // initialiser on mount. A new turn unmounts + remounts the indicator
  // because the parent gates it on ``activeRequestId``.
  const [pickedVerb] = useState(() => verb ?? pickVerb());
  const [tick, setTick] = useState(0);
  const tokenCounterRef = useRef(0);

  // Single 50 ms clock — matches free-code's ``useAnimationFrame(50)``.
  useEffect(() => {
    const handle = setInterval(() => {
      setTick((t) => t + 1);
    }, TICK_INTERVAL_MS);
    return () => clearInterval(handle);
  }, []);

  // Smooth the token counter on every tick. Mutating a ref outside an
  // effect is fine here because the next render reads the new value
  // and we want it computed before the JSX runs (otherwise the display
  // lags by one frame).
  if (tokenCounterRef.current < targetTokens) {
    const gap = targetTokens - tokenCounterRef.current;
    const step = gap < 70 ? 3 : gap < 200 ? Math.max(8, Math.ceil(gap * 0.15)) : 50;
    tokenCounterRef.current = Math.min(tokenCounterRef.current + step, targetTokens);
  } else if (tokenCounterRef.current > targetTokens) {
    // Target shrinks (rare — e.g. session reset) → snap.
    tokenCounterRef.current = targetTokens;
  }

  const time = tick * TICK_INTERVAL_MS;
  const frameIdx = Math.floor(time / FRAME_INTERVAL_MS) % FRAMES.length;
  const frame = FRAMES[frameIdx];
  const elapsedMs = Date.now() - startedAt;

  const segments: string[] = [formatDuration(elapsedMs)];
  if (tokenCounterRef.current > 0) {
    segments.push(`↓ ${formatTokens(tokenCounterRef.current)} tokens`);
  }
  segments.push(
    thoughtForMs > 0
      ? `thought for ${formatDuration(thoughtForMs)}`
      : "thinking…",
  );

  return (
    <Text>
      <Text color={THEME.claude}>{frame} </Text>
      <Text color={THEME.claude}>{pickedVerb}…</Text>
      <Text color={THEME.subtle} dimColor>
        {" ("}
        {segments.join(" · ")}
        {")"}
      </Text>
    </Text>
  );
}

// ---------------------------------------------------------------------------
// Format helpers
// ---------------------------------------------------------------------------

/**
 * Multi-unit duration formatter mirroring free-code's
 * ``formatDuration``. Hides trailing zero components (``2m`` not
 * ``2m 0s``); collapses to the most-significant unit only when both
 * sub-units are zero.
 */
export function formatDuration(ms: number): string {
  if (ms < 60_000) {
    const s = Math.max(0, Math.floor(ms / 1000));
    return `${s}s`;
  }
  let hours = Math.floor(ms / 3_600_000);
  let minutes = Math.floor((ms % 3_600_000) / 60_000);
  let seconds = Math.round((ms % 60_000) / 1000);
  // Carry over rounding (e.g. 59.7s → 1m 0s).
  if (seconds === 60) {
    seconds = 0;
    minutes += 1;
  }
  if (minutes === 60) {
    minutes = 0;
    hours += 1;
  }
  if (hours > 0) {
    if (minutes === 0 && seconds === 0) return `${hours}h`;
    if (seconds === 0) return `${hours}h ${minutes}m`;
    return `${hours}h ${minutes}m ${seconds}s`;
  }
  if (seconds === 0) return `${minutes}m`;
  return `${minutes}m ${seconds}s`;
}

/** ``1500`` → ``1.5k``; ``45`` → ``45``; ``150_000`` → ``150k``. */
export function formatTokens(n: number): string {
  if (n < 1000) return String(n);
  if (n < 10_000) return `${(n / 1000).toFixed(1)}k`;
  return `${Math.round(n / 1000)}k`;
}
