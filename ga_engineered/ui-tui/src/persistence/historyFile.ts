/**
 * Persistent input history.
 *
 * Each entry is one JSON line with shape ``{ts, mode, text}``. We append
 * synchronously on submit (called rarely enough that I/O cost is fine)
 * and read once at startup. Older logs survive forever; the file is
 * never truncated by the TUI itself — leave that to the user.
 */

import { existsSync, mkdirSync, readFileSync, appendFileSync } from "node:fs";
import { dirname } from "node:path";

import type { HistoryEntry, InputMode } from "../hooks/useInputHistory.js";

interface PersistedRow {
  ts: number;
  mode: InputMode;
  text: string;
}

export function defaultHistoryPath(): string {
  const home = process.env["GENERIC_AGENT_HOME"];
  if (home && home.length > 0) return `${home.replace(/\/$/, "")}/history.jsonl`;
  const fallback = process.env["HOME"] ?? "/tmp";
  return `${fallback}/.generic-agent/history.jsonl`;
}

export function loadHistory(path: string = defaultHistoryPath()): HistoryEntry[] {
  if (!existsSync(path)) return [];
  try {
    const text = readFileSync(path, "utf-8");
    const rows: HistoryEntry[] = [];
    for (const line of text.split("\n")) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      try {
        const parsed = JSON.parse(trimmed) as PersistedRow;
        if (
          parsed &&
          typeof parsed.text === "string" &&
          (parsed.mode === "chat" || parsed.mode === "bash")
        ) {
          rows.push({ mode: parsed.mode, text: parsed.text });
        }
      } catch {
        // ignore malformed lines
      }
    }
    return rows;
  } catch {
    return [];
  }
}

export function appendHistory(
  entry: HistoryEntry,
  path: string = defaultHistoryPath(),
): void {
  try {
    const dir = dirname(path);
    if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
    const row: PersistedRow = { ts: Date.now(), ...entry };
    appendFileSync(path, JSON.stringify(row) + "\n", { encoding: "utf-8" });
  } catch {
    // Persistence is best-effort; the in-memory history still works.
  }
}
