/**
 * Render a parsed markdown :class:`Document` into Ink elements.
 *
 * The output is a single flat ``<Box>`` of ``<Text>`` rows. Inline
 * nodes are recursively rendered with chalk-style colour /
 * weight props.
 */

import { Box, Text } from "ink";
import React from "react";

import { THEME } from "../theme.js";
import { type Document, type Node, parseInline, parseMarkdown } from "./parser.js";
import { padVisual, visualWidth, wrapVisual } from "./visualWidth.js";

export interface MarkdownProps {
  source: string;
  /** Optional max width — currently ignored, Ink wraps for us. */
  width?: number;
  /** Optional inline tail for streaming cursors. */
  suffix?: React.ReactNode;
}

export function Markdown({ source, suffix }: MarkdownProps): React.ReactElement {
  let document: Document;
  try {
    document = parseMarkdown(source);
  } catch {
    // Parser failure should never crash the transcript — fall back
    // to plain text.
    return <Text>{source}</Text>;
  }
  return (
    <Box flexDirection="column">
      {document.blocks.map((block, idx) => {
        const isLast = idx === document.blocks.length - 1;
        return <BlockRow key={idx} node={block} suffix={isLast ? suffix : null} />;
      })}
      {document.blocks.length === 0 && suffix ? <Text>{suffix}</Text> : null}
    </Box>
  );
}

function BlockRow({
  node,
  suffix,
}: {
  node: Node;
  suffix?: React.ReactNode;
}): React.ReactElement {
  switch (node.type) {
    case "code_block":
      return (
        <>
          <CodeBlock lang={node.lang} text={node.text} />
          {suffix ? <Text>{suffix}</Text> : null}
        </>
      );
    case "table":
      return (
        <>
          <TableBlock headers={node.headers} rows={node.rows} align={node.align} />
          {suffix ? <Text>{suffix}</Text> : null}
        </>
      );
    case "list":
      return (
        <Box flexDirection="column">
          {node.items.map((item, idx) => (
            <Box key={idx}>
              <Text color={THEME.subtle}>
                {node.ordered ? `${idx + 1}. ` : "  • "}
              </Text>
              <Box flexDirection="column" flexGrow={1}>
                <Text>
                  <InlineRun nodes={item.children} />
                  {idx === node.items.length - 1 ? suffix : null}
                </Text>
              </Box>
            </Box>
          ))}
        </Box>
      );
    case "heading": {
      // Free-code style (src/utils/markdown.ts:104): no literal ``#`` chars,
      // just bold/italic/underline depending on depth so the heading reads
      // as a heading instead of a paragraph that starts with hashes.
      const color =
        node.level === 1 ? THEME.claude : node.level === 2 ? THEME.startupAccent : THEME.suggestion;
      return (
        <Box marginTop={node.level === 1 ? 1 : 0}>
          <Text bold italic={node.level === 1} underline={node.level === 1} color={color}>
            <InlineRun nodes={node.children} />
            {suffix}
          </Text>
        </Box>
      );
    }
    case "paragraph":
      // A paragraph is one ``<Text>`` so Ink wraps the inline run as a
      // single flow rather than breaking each inline node onto its own
      // line.
      return (
        <Text>
          <InlineRun nodes={node.children} />
          {suffix}
        </Text>
      );
    case "blank":
      return <Text> {suffix}</Text>;
    case "hr": {
      // Render ``---`` / ``***`` / ``___`` as a dim box-drawing line.
      // Free-code (utils/markdown.ts:137) just returns the literal
      // ``---``; we go a step further with a unicode rule because the
      // separator in a chat transcript reads better as a visible line.
      const width = Math.max(8, Math.min(60, (process.stdout.columns ?? 80) - 4));
      return (
        <Text color={THEME.subtle} dimColor>
          {"─".repeat(width)}
          {suffix}
        </Text>
      );
    }
    case "text":
      return <Text>{node.text}{suffix}</Text>;
    default:
      return (
        <Text>
          <InlineRun nodes={[node]} />
          {suffix}
        </Text>
      );
  }
}

function TableBlock({
  headers,
  rows,
  align,
}: {
  headers: string[];
  rows: string[][];
  align: Array<"left" | "right" | "center">;
}): React.ReactElement {
  const widths = computeColumnWidths(headers, rows, align);

  const top = "┌" + widths.map((w) => "─".repeat(w + 2)).join("┬") + "┐";
  const mid = "├" + widths.map((w) => "─".repeat(w + 2)).join("┼") + "┤";
  const bot = "└" + widths.map((w) => "─".repeat(w + 2)).join("┴") + "┘";

  // Render each row as one ``<Text>`` node containing a single string —
  // ANSI colour codes for inline runs are applied inline. This avoids
  // Ink's flex layout reflowing cell fragments, which used to misalign
  // wide-character cells (CJK, emoji).
  const headerRow = renderRowLines(
    headers.map((h) => stripInlineMarkers(h)),
    widths,
    align,
    true,
  );
  const dataRows = rows.map((row) =>
    renderRowLines(
      row.map((c) => stripInlineMarkers(c)),
      widths,
      align,
      false,
    ),
  );

  return (
    <Box flexDirection="column" marginY={1}>
      <Text color={THEME.subtle} dimColor>{top}</Text>
      {headerRow.map((line, i) => (
        <Text key={`h-${i}`} color={THEME.subtle} dimColor>
          {line}
        </Text>
      ))}
      <Text color={THEME.subtle} dimColor>{mid}</Text>
      {dataRows.flatMap((row, ridx) =>
        row.map((line, lidx) => (
          <Text key={`r-${ridx}-${lidx}`} color={THEME.subtle} dimColor>
            {line}
          </Text>
        )),
      )}
      <Text color={THEME.subtle} dimColor>{bot}</Text>
    </Box>
  );
}

/**
 * Free-code-style column width algorithm:
 *   - For each column, measure the longest *word* width and the *full*
 *     content width (visual, not codepoint-count, so CJK = 2 cols).
 *   - If the table fits at ideal widths, use them.
 *   - If not, give every column its min and distribute the leftover
 *     space proportionally to how much each column wanted.
 *   - If even at min widths we overflow, scale all columns down.
 *
 * Border overhead per row: ``│`` + per-column ``(2-space padding +
 * cell + ``│``)`` = 1 + 3 * numCols.
 */
function computeColumnWidths(
  headers: string[],
  rows: string[][],
  align: Array<"left" | "right" | "center">,
): number[] {
  void align;
  const numCols = headers.length;
  const TERMINAL_WIDTH = (process.stdout.columns ?? 100) - 4;
  const MIN_W = 3;

  const minWidths: number[] = headers.map((h, i) => {
    const all = [h, ...rows.map((r) => r[i] ?? "")];
    let w = 0;
    for (const cell of all) {
      const stripped = stripInlineMarkers(cell);
      const longest = Math.max(
        ...stripped.split(/\s+/).map((tok) => visualWidth(tok)),
        MIN_W,
      );
      w = Math.max(w, longest);
    }
    return w;
  });

  const idealWidths: number[] = headers.map((h, i) => {
    const all = [h, ...rows.map((r) => r[i] ?? "")];
    return Math.max(
      MIN_W,
      ...all.map((cell) => visualWidth(stripInlineMarkers(cell))),
    );
  });

  const overhead = 1 + numCols * 3;
  const available = Math.max(TERMINAL_WIDTH - overhead, numCols * MIN_W);
  const totalIdeal = idealWidths.reduce((a, b) => a + b, 0);
  const totalMin = minWidths.reduce((a, b) => a + b, 0);

  if (totalIdeal <= available) return idealWidths;
  if (totalMin <= available) {
    const extra = available - totalMin;
    const overflows = idealWidths.map((ideal, i) => ideal - (minWidths[i] ?? 0));
    const totalOverflow = overflows.reduce((a, b) => a + b, 0);
    if (totalOverflow === 0) return minWidths;
    return minWidths.map((min, i) => {
      const share = Math.floor(((overflows[i] ?? 0) / totalOverflow) * extra);
      return min + share;
    });
  }
  const scale = available / totalMin;
  return minWidths.map((w) => Math.max(MIN_W, Math.floor(w * scale)));
}

/**
 * Render one row to one or more strings (one per visual line) with the
 * borders + padding baked in. Multi-line cells are vertically aligned
 * to the top — free-code centres them, but for chat transcripts the
 * top is more natural since cells rarely need vertical centring.
 */
function renderRowLines(
  cells: string[],
  widths: number[],
  align: Array<"left" | "right" | "center">,
  isHeader: boolean,
): string[] {
  const wrapped = cells.map((cell, i) => wrapVisual(cell, widths[i] ?? 0));
  const maxLines = Math.max(1, ...wrapped.map((lines) => lines.length));

  const out: string[] = [];
  for (let lineIdx = 0; lineIdx < maxLines; lineIdx++) {
    let line = "│";
    for (let col = 0; col < cells.length; col++) {
      const cellLines = wrapped[col] ?? [""];
      const text = cellLines[lineIdx] ?? "";
      const w = widths[col] ?? 0;
      const a = isHeader ? "center" : align[col] ?? "left";
      line += " " + padVisual(text, w, a) + " │";
    }
    out.push(line);
  }
  return out;
}

function stripInlineMarkers(text: string): string {
  // Remove ``** ** `` ``` *` and `[label](url)` -> "label"
  return text
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/\*([^*]+)\*/g, "$1")
    .replace(/`([^`]+)`/g, "$1");
}

function CodeBlock({ lang, text }: { lang: string; text: string }): React.ReactElement {
  return (
    <Box flexDirection="column" marginY={1}>
      {lang ? (
        <Text color="gray" dimColor>
          {"  ╭── "}
          <Text color="cyan">{lang}</Text>
          {" ──"}
        </Text>
      ) : (
        <Text color="gray" dimColor>
          {"  ╭──"}
        </Text>
      )}
      {text.split("\n").map((line, idx) => (
        <Text key={idx} color="gray">
          {"  │ "}
          <Text color="white">{line}</Text>
        </Text>
      ))}
      <Text color="gray" dimColor>
        {"  ╰──"}
      </Text>
    </Box>
  );
}

function InlineRun({ nodes }: { nodes: Node[] }): React.ReactElement {
  return (
    <>
      {nodes.map((node, idx) => (
        <InlineNode key={idx} node={node} />
      ))}
    </>
  );
}

function InlineNode({ node }: { node: Node }): React.ReactElement {
  switch (node.type) {
    case "text":
      return <Text>{node.text}</Text>;
    case "bold":
      return (
        <Text bold>
          <InlineRun nodes={node.children} />
        </Text>
      );
    case "italic":
      return (
        <Text italic>
          <InlineRun nodes={node.children} />
        </Text>
      );
    case "code":
      // Inline code: claude orange, no background and no padding spaces
      // so the highlight stays inline within the surrounding paragraph
      // text — matches free-code's chalk-style accent.
      return <Text color={THEME.claude}>{node.text}</Text>;
    case "link":
      return (
        <Text underline color={THEME.suggestion}>
          {node.text}
          <Text color={THEME.subtle} dimColor>
            {" ("}
            {node.href}
            {")"}
          </Text>
        </Text>
      );
    case "heading":
      return (
        <Text bold>
          <InlineRun nodes={node.children} />
        </Text>
      );
    case "code_block":
      // Should never happen at inline level, but render safely.
      return <Text>{node.text}</Text>;
    case "table":
      // Tables don't appear inline; render as a fallback.
      return <Text>{node.headers.join(" | ")}</Text>;
    case "paragraph":
      return (
        <Text>
          <InlineRun nodes={node.children} />
        </Text>
      );
    case "blank":
      return <Text> </Text>;
    case "hr":
      // Should never happen at inline level, but render as fallback.
      return <Text>{"───"}</Text>;
    case "list":
      // Should never happen at inline level, but render as fallback.
      return (
        <Text>
          {node.items.map((item) => `• ${nodesToText(item.children)}`).join("  ")}
        </Text>
      );
  }
}

function nodesToText(nodes: Node[]): string {
  return nodes
    .map((n) => {
      if (n.type === "text") return n.text;
      if (n.type === "code") return n.text;
      if (n.type === "bold" || n.type === "italic") return nodesToText(n.children);
      return "";
    })
    .join("");
}
