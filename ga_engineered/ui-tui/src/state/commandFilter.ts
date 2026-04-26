/**
 * Pure helpers for slash-command autocomplete.
 *
 * Kept framework-agnostic so the matching/scoring logic can be unit
 * tested without rendering Ink. The reducer-style separation mirrors
 * ``transcriptStore`` and ``schemas``.
 */

import type { CommandDef } from "../schemas.js";

/**
 * Return commands whose ``name`` (or one of their ``aliases``) starts
 * with the user's draft (after the leading slash). Sorted by match
 * quality: exact-prefix on name first, then alias, then by category.
 *
 * If ``query`` is just "/" the full list is returned in registry order.
 */
export function filterCommands(
  commands: readonly CommandDef[],
  query: string,
): CommandDef[] {
  if (!query.startsWith("/")) return [];
  const term = query.slice(1).trim().toLowerCase();
  if (term.length === 0) return [...commands];

  const scored: Array<{ command: CommandDef; score: number }> = [];
  for (const command of commands) {
    const score = scoreCommand(command, term);
    if (score >= 0) scored.push({ command, score });
  }
  scored.sort((a, b) => {
    if (a.score !== b.score) return b.score - a.score;
    return a.command.name.localeCompare(b.command.name);
  });
  return scored.map((entry) => entry.command);
}

/**
 * Score a single command against a search term. Higher is better.
 *  - 100: exact match on name
 *  - 90:  name starts with term
 *  - 80:  alias exact match (best across all aliases)
 *  - 70:  alias starts with term (best across all aliases)
 *  - 50:  name contains term as a substring
 *  - 30:  alias contains term as a substring
 *  - -1:  no match (caller filters out)
 *
 * The alias loops scan *all* aliases and keep the best score, rather
 * than returning on the first match. Otherwise an alias array of
 * ``["qu", "q"]`` queried with ``"q"`` would return the prefix score
 * (70) instead of the better exact score (80).
 */
function scoreCommand(command: CommandDef, term: string): number {
  const name = command.name.toLowerCase();
  if (name === term) return 100;
  if (name.startsWith(term)) return 90;

  let aliasScore = -1;
  for (const alias of command.aliases) {
    const lower = alias.toLowerCase();
    if (lower === term) {
      aliasScore = Math.max(aliasScore, 80);
    } else if (lower.startsWith(term)) {
      aliasScore = Math.max(aliasScore, 70);
    } else if (lower.includes(term)) {
      aliasScore = Math.max(aliasScore, 30);
    }
  }
  if (aliasScore >= 70) return aliasScore;

  if (name.includes(term)) return 50;
  if (aliasScore >= 0) return aliasScore;
  return -1;
}

/** Compose the completion that should replace the draft when Tab is pressed. */
export function applyCompletion(command: CommandDef): string {
  return `/${command.name}${command.args_hint ? " " : ""}`;
}
