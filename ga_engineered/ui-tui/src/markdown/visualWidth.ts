/**
 * Visual width helpers — what Unicode width does a string take in a
 * monospaced terminal cell?
 *
 * - ASCII / Latin-1 letters: 1 cell
 * - CJK ideographs, hangul, fullwidth forms: 2 cells
 * - Common emoji (BMP outliers + SMP): 2 cells
 * - Combining marks / zero-width joiners: 0 cells
 *
 * The ranges below mirror the Unicode East-Asian-Width "F" + "W"
 * categories plus a hand-curated set of emoji and zero-width chars.
 * It's not as exhaustive as the ``string-width`` npm package, but it
 * handles the cases LLM responses actually emit and keeps us
 * dependency-free.
 */

const ZERO_WIDTH = [
  [0x200b, 0x200f],
  [0x202a, 0x202e],
  [0xfe00, 0xfe0f],
  [0x1f3fb, 0x1f3ff], // emoji skin tone modifiers
];

const DOUBLE_WIDTH = [
  [0x1100, 0x115f], // Hangul Jamo
  [0x2329, 0x232a],
  [0x2e80, 0x303e], // CJK radicals + symbols
  [0x3041, 0x33ff], // Hiragana / Katakana / Bopomofo / CJK
  [0x3400, 0x4dbf], // CJK Unified Ideographs Ext A
  [0x4e00, 0x9fff], // CJK Unified Ideographs
  [0xa000, 0xa4cf], // Yi Syllables
  [0xac00, 0xd7a3], // Hangul Syllables
  [0xf900, 0xfaff], // CJK Compatibility Ideographs
  [0xfe30, 0xfe4f], // CJK Compatibility Forms
  [0xff00, 0xff60], // Fullwidth Forms
  [0xffe0, 0xffe6],
  [0x1f300, 0x1f64f], // Emoji
  [0x1f680, 0x1f6ff],
  [0x1f900, 0x1f9ff], // Supplemental Symbols and Pictographs
  [0x20000, 0x2fffd], // CJK Ext B+
  [0x30000, 0x3fffd],
];

const inRange = (code: number, ranges: number[][]): boolean => {
  for (const [lo, hi] of ranges) {
    if (code >= (lo ?? 0) && code <= (hi ?? 0)) return true;
  }
  return false;
};

export function charWidth(codePoint: number): number {
  if (inRange(codePoint, ZERO_WIDTH)) return 0;
  if (inRange(codePoint, DOUBLE_WIDTH)) return 2;
  return 1;
}

export function visualWidth(text: string): number {
  let w = 0;
  for (const ch of text) {
    const cp = ch.codePointAt(0) ?? 0;
    w += charWidth(cp);
  }
  return w;
}

/** Pad a string with spaces so its visual width equals ``width``. */
export function padVisual(
  text: string,
  width: number,
  align: "left" | "right" | "center",
): string {
  const w = visualWidth(text);
  if (w >= width) return text;
  const pad = width - w;
  if (align === "right") return " ".repeat(pad) + text;
  if (align === "center") {
    const left = Math.floor(pad / 2);
    return " ".repeat(left) + text + " ".repeat(pad - left);
  }
  return text + " ".repeat(pad);
}

/** Word-wrap by visual width. Hard-breaks individual words that exceed ``width``. */
export function wrapVisual(text: string, width: number): string[] {
  if (width <= 0) return [text];
  const lines: string[] = [];
  let line = "";
  let lineWidth = 0;

  // Tokenise by words but keep each character iteratable as a code point.
  const flush = (): void => {
    if (line.length > 0) {
      lines.push(line);
      line = "";
      lineWidth = 0;
    }
  };

  const tokens = text.split(/(\s+)/);
  for (const token of tokens) {
    if (token.length === 0) continue;
    const tokenWidth = visualWidth(token);
    if (/^\s+$/.test(token)) {
      // Whitespace token: only push if the line has content.
      if (lineWidth === 0) continue;
      if (lineWidth + tokenWidth > width) {
        flush();
        continue;
      }
      line += token;
      lineWidth += tokenWidth;
      continue;
    }
    if (tokenWidth > width) {
      // Hard break a too-long token.
      flush();
      let chunk = "";
      let chunkWidth = 0;
      for (const ch of token) {
        const cw = charWidth(ch.codePointAt(0) ?? 0);
        if (chunkWidth + cw > width) {
          lines.push(chunk);
          chunk = ch;
          chunkWidth = cw;
        } else {
          chunk += ch;
          chunkWidth += cw;
        }
      }
      if (chunk.length > 0) {
        line = chunk;
        lineWidth = chunkWidth;
      }
      continue;
    }
    if (lineWidth + tokenWidth > width) {
      flush();
    }
    line += token;
    lineWidth += tokenWidth;
  }
  flush();
  return lines.length === 0 ? [""] : lines;
}
