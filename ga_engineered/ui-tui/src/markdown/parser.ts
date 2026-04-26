/**
 * Tiny markdown parser for assistant messages.
 *
 * The goal is to render the small subset of markdown LLMs typically
 * emit: bold, italic, inline code, headings, code blocks, and bare
 * links. We do NOT handle nested blockquotes, tables, lists with
 * inline formatting inside, or every CommonMark edge case — that
 * would mean dragging in a 200KB markdown library for marginal gains.
 *
 * The output is a flat array of typed nodes. The renderer walks it
 * and maps each node onto Ink ``<Text>`` elements.
 */

export type Node =
  | { type: "text"; text: string }
  | { type: "bold"; children: Node[] }
  | { type: "italic"; children: Node[] }
  | { type: "code"; text: string }
  | { type: "link"; text: string; href: string }
  | { type: "heading"; level: 1 | 2 | 3 | 4 | 5 | 6; children: Node[] }
  | { type: "code_block"; lang: string; text: string }
  | { type: "paragraph"; children: Node[] }
  | { type: "blank" }
  | { type: "hr" }
  | { type: "list"; ordered: boolean; items: ListItem[] }
  | {
      type: "table";
      headers: string[];
      rows: string[][];
      align: ("left" | "right" | "center")[];
    };

export interface ListItem {
  children: Node[];
}

export interface Document {
  blocks: Node[];
}

export function parseMarkdown(source: string): Document {
  const blocks: Node[] = [];
  const lines = source.split("\n");
  let i = 0;
  while (i < lines.length) {
    const line = lines[i] ?? "";

    // Code fence — accumulate until closing fence.
    const fenceMatch = /^```(\w*)\s*$/.exec(line);
    if (fenceMatch) {
      const lang = fenceMatch[1] ?? "";
      const buf: string[] = [];
      i += 1;
      while (i < lines.length && !/^```\s*$/.test(lines[i] ?? "")) {
        buf.push(lines[i] ?? "");
        i += 1;
      }
      if (i < lines.length) i += 1; // skip closing fence
      blocks.push({ type: "code_block", lang, text: buf.join("\n") });
      continue;
    }

    // Heading.
    const headingMatch = /^(#{1,6})\s+(.+)$/.exec(line);
    if (headingMatch) {
      const level = headingMatch[1]?.length as 1 | 2 | 3 | 4 | 5 | 6;
      const text = headingMatch[2] ?? "";
      blocks.push({ type: "heading", level, children: parseInline(text) });
      i += 1;
      continue;
    }

    // Markdown table — header row with pipes, then a separator row of
    // dashes/colons, then data rows. Bail at the first non-pipe line.
    if (line.includes("|") && i + 1 < lines.length && /^\s*\|?[\s:|-]+\|/.test(lines[i + 1] ?? "")) {
      const headerCells = splitCells(line);
      const separatorCells = splitCells(lines[i + 1] ?? "");
      const align = separatorCells.map(parseAlignment);
      const rows: string[][] = [];
      i += 2;
      while (i < lines.length && (lines[i] ?? "").includes("|")) {
        rows.push(splitCells(lines[i] ?? ""));
        i += 1;
      }
      blocks.push({
        type: "table",
        headers: headerCells,
        rows,
        align,
      });
      continue;
    }

    // Blank line → paragraph spacer.
    if (line.trim().length === 0) {
      blocks.push({ type: "blank" });
      i += 1;
      continue;
    }

    // Horizontal rule: three or more ``-``, ``*``, or ``_`` on a line.
    // Must come before the list branch — ``- foo`` is a list item, but
    // bare ``---`` is an hr and used to fall through to a paragraph
    // that just printed the dashes literally.
    if (/^\s{0,3}(?:-{3,}|\*{3,}|_{3,})\s*$/.test(line)) {
      blocks.push({ type: "hr" });
      i += 1;
      continue;
    }

    // Markdown list: ``- item`` / ``* item`` / ``+ item`` / ``1. item``.
    // Without this, consecutive list lines collapse into a single
    // paragraph because the paragraph branch joins them with spaces.
    const listMatch = LIST_ITEM_RE.exec(line);
    if (listMatch) {
      const ordered = /^\d/.test(listMatch[2] ?? "");
      const items: ListItem[] = [];
      while (i < lines.length) {
        const ln = lines[i] ?? "";
        const m = LIST_ITEM_RE.exec(ln);
        if (m) {
          items.push({ children: parseInline(m[3] ?? "") });
          i += 1;
          continue;
        }
        // Continuation line: indented non-blank content under the
        // current item gets appended to it as soft-break text.
        if (
          items.length > 0 &&
          ln.length > 0 &&
          /^\s+/.test(ln) &&
          ln.trim().length > 0
        ) {
          const last = items[items.length - 1];
          if (last) {
            last.children.push({ type: "text", text: " " + ln.trim() });
          }
          i += 1;
          continue;
        }
        break;
      }
      blocks.push({ type: "list", ordered, items });
      continue;
    }

    // Plain paragraph — accumulate consecutive non-blank lines and emit
    // a single ``paragraph`` block containing the inline run. Wrapping
    // every inline node as a top-level block forced Ink to render each
    // one as its own row, which broke ``inline `code` `` styling onto
    // separate lines.
    const paragraph: string[] = [line];
    i += 1;
    while (
      i < lines.length &&
      lines[i] !== undefined &&
      (lines[i] ?? "").trim().length > 0 &&
      !/^```/.test(lines[i] ?? "") &&
      !/^#{1,3}\s/.test(lines[i] ?? "") &&
      !LIST_ITEM_RE.test(lines[i] ?? "")
    ) {
      paragraph.push(lines[i] ?? "");
      i += 1;
    }
    blocks.push({
      type: "paragraph",
      children: parseInline(paragraph.join(" ")),
    });
  }

  return { blocks };
}

// ---------------------------------------------------------------------------
// Inline parsing
// ---------------------------------------------------------------------------

const INLINE_RE = /(\*\*([^*]+)\*\*|\*([^*]+)\*|`([^`]+)`|\[([^\]]+)\]\(([^)]+)\))/g;

/**
 * Bullet markers: ``-``, ``*``, ``+``, ``1.``, ``2.`` etc. Capture the
 * leading whitespace, the marker, and the rest of the line (the item
 * text). The asterisk form is intentionally restricted by requiring a
 * trailing space so we don't false-match on emphasis (``*bold*``).
 */
const LIST_ITEM_RE = /^(\s*)([-*+]|\d+\.)\s+(.*)$/;

function splitCells(line: string): string[] {
  // Strip leading/trailing pipe + whitespace, then split on internal pipes.
  const trimmed = line.trim().replace(/^\||\|$/g, "");
  return trimmed.split("|").map((cell) => cell.trim());
}

function parseAlignment(separatorCell: string): "left" | "right" | "center" {
  const trimmed = separatorCell.trim();
  const startsColon = trimmed.startsWith(":");
  const endsColon = trimmed.endsWith(":");
  if (startsColon && endsColon) return "center";
  if (endsColon) return "right";
  return "left";
}

export function parseInline(text: string): Node[] {
  const out: Node[] = [];
  let cursor = 0;
  for (const match of text.matchAll(INLINE_RE)) {
    const start = match.index ?? 0;
    if (start > cursor) {
      out.push({ type: "text", text: text.slice(cursor, start) });
    }
    if (match[2] !== undefined) {
      out.push({ type: "bold", children: parseInline(match[2]) });
    } else if (match[3] !== undefined) {
      out.push({ type: "italic", children: parseInline(match[3]) });
    } else if (match[4] !== undefined) {
      out.push({ type: "code", text: match[4] });
    } else if (match[5] !== undefined && match[6] !== undefined) {
      out.push({ type: "link", text: match[5], href: match[6] });
    }
    cursor = start + match[0].length;
  }
  if (cursor < text.length) {
    out.push({ type: "text", text: text.slice(cursor) });
  }
  return out;
}
