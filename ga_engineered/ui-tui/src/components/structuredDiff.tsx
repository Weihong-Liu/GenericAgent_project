import { Box, Text } from "ink";
import React from "react";

interface StructuredDiffProps {
  diff: string;
  maxLines?: number;
}

export type DiffLineKind = "header" | "hunk" | "add" | "remove" | "context";

export interface DiffLine {
  kind: DiffLineKind;
  text: string;
}

export function StructuredDiff({
  diff,
  maxLines = 120,
}: StructuredDiffProps): React.ReactElement {
  const lines = parseUnifiedDiff(diff);
  const visible = lines.slice(0, maxLines);
  const hidden = Math.max(0, lines.length - visible.length);

  return (
    <Box flexDirection="column">
      {visible.map((line, idx) => (
        <Text key={idx} color={diffColor(line.kind)} dimColor={line.kind === "context"}>
          {linePrefix(line.kind)}
          {line.text}
        </Text>
      ))}
      {hidden > 0 ? (
        <Text color="gray" dimColor>
          … {hidden} diff lines hidden
        </Text>
      ) : null}
    </Box>
  );
}

export function parseUnifiedDiff(diff: string): DiffLine[] {
  return diff.split("\n").map((text) => ({ text, kind: classifyDiffLine(text) }));
}

export function classifyDiffLine(line: string): DiffLineKind {
  if (
    line.startsWith("diff --git") ||
    line.startsWith("index ") ||
    line.startsWith("--- ") ||
    line.startsWith("+++ ")
  ) {
    return "header";
  }
  if (line.startsWith("@@")) return "hunk";
  if (line.startsWith("+")) return "add";
  if (line.startsWith("-")) return "remove";
  return "context";
}

function diffColor(kind: DiffLineKind): string {
  switch (kind) {
    case "add":
      return "green";
    case "remove":
      return "red";
    case "hunk":
      return "cyan";
    case "header":
      return "yellow";
    case "context":
      return "gray";
  }
}

function linePrefix(kind: DiffLineKind): string {
  switch (kind) {
    case "add":
      return "  + ";
    case "remove":
      return "  - ";
    case "hunk":
      return "  @ ";
    case "header":
      return "  # ";
    case "context":
      return "    ";
  }
}
