import { describe, expect, it } from "vitest";

import { parseInline, parseMarkdown } from "../markdown/parser.js";

describe("parseInline", () => {
  it("captures bold runs", () => {
    const nodes = parseInline("hello **world** foo");
    expect(nodes).toEqual([
      { type: "text", text: "hello " },
      {
        type: "bold",
        children: [{ type: "text", text: "world" }],
      },
      { type: "text", text: " foo" },
    ]);
  });

  it("captures italic runs", () => {
    const nodes = parseInline("a *b* c");
    expect(nodes[1]?.type).toBe("italic");
  });

  it("captures inline code", () => {
    const nodes = parseInline("type `npm test`");
    const code = nodes.find((n) => n.type === "code");
    expect(code).toEqual({ type: "code", text: "npm test" });
  });

  it("captures markdown links", () => {
    const nodes = parseInline("see [docs](https://example.org)");
    const link = nodes.find((n) => n.type === "link");
    expect(link).toEqual({
      type: "link",
      text: "docs",
      href: "https://example.org",
    });
  });

  it("preserves plain text untouched", () => {
    const nodes = parseInline("hello world");
    expect(nodes).toEqual([{ type: "text", text: "hello world" }]);
  });

  it("does not crash on unmatched markers", () => {
    const nodes = parseInline("**unterminated");
    expect(nodes).toEqual([{ type: "text", text: "**unterminated" }]);
  });
});

describe("parseMarkdown blocks", () => {
  it("parses headings at three levels", () => {
    const doc = parseMarkdown("# h1\n## h2\n### h3");
    const headings = doc.blocks.filter((b) => b.type === "heading");
    expect(headings.map((h) => (h as { level: number }).level)).toEqual([1, 2, 3]);
  });

  it("parses fenced code blocks with a language tag", () => {
    const doc = parseMarkdown("```ts\nconst x = 1;\nconst y = 2;\n```");
    const block = doc.blocks.find((b) => b.type === "code_block");
    expect(block).toEqual({
      type: "code_block",
      lang: "ts",
      text: "const x = 1;\nconst y = 2;",
    });
  });

  it("parses code blocks without a language tag", () => {
    const doc = parseMarkdown("```\nplain\n```");
    const block = doc.blocks.find((b) => b.type === "code_block");
    expect((block as { lang: string }).lang).toBe("");
  });

  it("treats plain paragraphs as a single paragraph block with inline children", () => {
    const doc = parseMarkdown("hello **world**");
    const para = doc.blocks.find((b) => b.type === "paragraph");
    expect(para).toBeDefined();
    if (para?.type === "paragraph") {
      const bold = para.children.find((c) => c.type === "bold");
      expect(bold).toBeDefined();
    }
  });

  it("renders inline code inside a paragraph without breaking the line", () => {
    const doc = parseMarkdown("uses `uv` for packaging");
    const para = doc.blocks.find((b) => b.type === "paragraph");
    if (para?.type !== "paragraph") throw new Error("paragraph expected");
    const kinds = para.children.map((c) => c.type);
    expect(kinds).toContain("code");
    // The text and code nodes must be siblings in one paragraph, not
    // separate top-level blocks.
    expect(kinds.filter((k) => k === "text").length).toBeGreaterThan(0);
  });

  it("does not crash on a half-open code fence", () => {
    expect(() => parseMarkdown("```ts\nstart\n")).not.toThrow();
  });

  it("parses a basic markdown table", () => {
    const source = [
      "| col1 | col2 |",
      "|------|------|",
      "| a    | 1    |",
      "| b    | 2    |",
    ].join("\n");
    const doc = parseMarkdown(source);
    const table = doc.blocks.find((b) => b.type === "table");
    expect(table).toBeDefined();
    if (table?.type === "table") {
      expect(table.headers).toEqual(["col1", "col2"]);
      expect(table.rows).toEqual([
        ["a", "1"],
        ["b", "2"],
      ]);
    }
  });

  it("recognises right- and center-aligned table columns", () => {
    const source = [
      "| left | center | right |",
      "|:-----|:------:|------:|",
      "| a | b | c |",
    ].join("\n");
    const doc = parseMarkdown(source);
    const table = doc.blocks.find((b) => b.type === "table");
    if (table?.type === "table") {
      expect(table.align).toEqual(["left", "center", "right"]);
    }
  });

  it("groups consecutive ``- item`` lines into a single list block", () => {
    const source = [
      "Things I can do:",
      "- 文件操作：读写文件",
      "- 代码运行：Python / Shell",
      "- 网页浏览：搜索 / 抓取",
    ].join("\n");
    const doc = parseMarkdown(source);
    const list = doc.blocks.find((b) => b.type === "list");
    expect(list).toBeDefined();
    if (list?.type === "list") {
      expect(list.ordered).toBe(false);
      expect(list.items).toHaveLength(3);
    }
  });

  it("recognises ordered ``1. item`` lists", () => {
    const doc = parseMarkdown("1. first\n2. second\n3. third");
    const list = doc.blocks.find((b) => b.type === "list");
    if (list?.type !== "list") throw new Error("expected list block");
    expect(list.ordered).toBe(true);
    expect(list.items).toHaveLength(3);
  });

  it("does not collapse list items into a paragraph", () => {
    // Regression: previously every line was joined with ``" "`` into a
    // single paragraph, hiding the bullet structure entirely.
    const doc = parseMarkdown("- A\n- B\n- C");
    expect(doc.blocks.some((b) => b.type === "paragraph")).toBe(false);
    expect(doc.blocks.some((b) => b.type === "list")).toBe(true);
  });

  it("does not crash on empty input", () => {
    expect(() => parseMarkdown("")).not.toThrow();
    const doc = parseMarkdown("");
    // An empty source produces at most one block; it may be either a
    // ``blank`` paragraph spacer or nothing.
    expect(doc.blocks.length).toBeLessThanOrEqual(1);
    if (doc.blocks.length === 1) {
      expect(["blank", "text"]).toContain(doc.blocks[0]?.type);
    }
  });
});
