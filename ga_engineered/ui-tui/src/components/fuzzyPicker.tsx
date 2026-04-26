import { Text } from "ink";
import React from "react";

export interface FuzzyPickerItem {
  id: string;
  label: string;
  description?: string;
  hint?: string;
}

export interface ScoredFuzzyItem<T extends FuzzyPickerItem> {
  item: T;
  score: number;
  ranges: readonly [number, number][];
}

export interface FuzzyPickerProps<T extends FuzzyPickerItem> {
  items: readonly T[];
  selectedIndex: number;
  accentColor?: string;
  maxRows?: number;
  emptyLabel?: string;
  overflowLabel?: (count: number) => string;
}

export function FuzzyPicker<T extends FuzzyPickerItem>({
  items,
  selectedIndex,
  accentColor = "cyan",
  maxRows = 8,
  emptyLabel = "no matches",
  overflowLabel = (count) => `  …and ${count} more`,
}: FuzzyPickerProps<T>): React.ReactElement {
  const visible = items.slice(0, maxRows);
  const overflow = Math.max(0, items.length - visible.length);

  if (visible.length === 0) {
    return (
      <Text color="gray" dimColor>
        {emptyLabel}
      </Text>
    );
  }

  return (
    <>
      {visible.map((item, idx) => {
        const isActive = idx === selectedIndex;
        return (
          <Text key={item.id} color={isActive ? accentColor : "white"}>
            {isActive ? "❯ " : "  "}
            <Text bold={isActive}>{item.label}</Text>
            {item.hint ? <Text color="gray"> {item.hint}</Text> : null}
            {item.description ? (
              <>
                {"  "}
                <Text color="gray" dimColor>
                  {item.description}
                </Text>
              </>
            ) : null}
          </Text>
        );
      })}
      {overflow > 0 ? (
        <Text color="gray" dimColor>
          {overflowLabel(overflow)}
        </Text>
      ) : null}
    </>
  );
}

export function filterFuzzyItems<T extends FuzzyPickerItem>(
  items: readonly T[],
  query: string,
): ScoredFuzzyItem<T>[] {
  const normalized = query.trim().toLowerCase();
  if (!normalized) {
    return items.map((item, index) => ({
      item,
      score: index,
      ranges: [],
    }));
  }

  const scored: ScoredFuzzyItem<T>[] = [];
  for (const [index, item] of items.entries()) {
    const haystack = `${item.label} ${item.hint ?? ""} ${item.description ?? ""}`.toLowerCase();
    const match = scoreFuzzy(haystack, normalized);
    if (!match) continue;
    scored.push({
      item,
      score: match.score + index / 1000,
      ranges: match.ranges,
    });
  }
  scored.sort((a, b) => a.score - b.score);
  return scored;
}

export function clampSelection(index: number, itemCount: number): number {
  if (itemCount <= 0) return 0;
  return Math.min(Math.max(0, index), itemCount - 1);
}

function scoreFuzzy(haystack: string, needle: string): { score: number; ranges: readonly [number, number][] } | null {
  let cursor = 0;
  let score = 0;
  const ranges: [number, number][] = [];

  for (const char of needle) {
    const found = haystack.indexOf(char, cursor);
    if (found === -1) return null;
    score += found === cursor ? 0 : found - cursor + 1;
    ranges.push([found, found + 1]);
    cursor = found + 1;
  }

  return { score, ranges };
}
