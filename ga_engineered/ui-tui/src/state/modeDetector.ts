/**
 * Detect input mode from the draft text.
 *
 * Modes are mutually exclusive:
 *   - ``slash``  — starts with ``/``: slash overlay handles it.
 *   - ``bash``   — starts with ``!``: submit through ``tools.run("shell")``.
 *   - ``mention``— contains an *active* ``@<query>`` token at the cursor:
 *                  file picker overlay handles it.
 *   - ``chat``   — plain text.
 *
 * "active mention" means the most recent ``@`` in the buffer, with no
 * whitespace between it and the cursor — i.e. the user is typing the
 * query right now. This lets the overlay close as soon as the user
 * commits a path or types a space.
 */

export type InputMode = "chat" | "bash" | "slash" | "mention";

export interface MentionToken {
  /** Offset of the leading ``@`` character. */
  start: number;
  /** Offset just past the last query char (== cursor when active). */
  end: number;
  /** The text between ``@`` and the cursor. */
  query: string;
}

export function detectMode(value: string, cursor: number = value.length): InputMode {
  if (value.startsWith("/")) return "slash";
  if (value.startsWith("!")) return "bash";
  if (activeMention(value, cursor) !== null) return "mention";
  return "chat";
}

export function activeMention(value: string, cursor: number = value.length): MentionToken | null {
  // Walk backward from the cursor; bail when we hit whitespace or
  // start of buffer with no ``@``.
  let i = cursor;
  while (i > 0) {
    const ch = value[i - 1];
    if (ch === " " || ch === "\n" || ch === "\t") return null;
    if (ch === "@") {
      return { start: i - 1, end: cursor, query: value.slice(i, cursor) };
    }
    i -= 1;
  }
  return null;
}

/** Replace the active mention token with the picked path, plus a space. */
export function applyMention(value: string, cursor: number, path: string): {
  value: string;
  cursor: number;
} {
  const token = activeMention(value, cursor);
  if (!token) return { value, cursor };
  const before = value.slice(0, token.start);
  const after = value.slice(token.end);
  const inserted = `@${path} `;
  return {
    value: before + inserted + after,
    cursor: before.length + inserted.length,
  };
}
