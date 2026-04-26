type JsonObject = Record<string, unknown>;

export interface CollapsedPreview {
  lines: string[];
  hiddenLines: number;
}

/**
 * Free-code-style human-readable verb for a tool's result. Browser tools need
 * payload-aware summaries because their backend result is a single JSON line.
 */
export function summariseToolResult(toolName: string, raw: string, isError = false): string {
  const lines = raw.split("\n").length;
  const chars = raw.length;
  if (isError) {
    return `Errored (${chars} chars, ${lines} lines)`;
  }
  switch (toolName) {
    case "shell":
    case "code_run":
      return `Ran command (${lines} lines)`;
    case "file_read":
      return `Read ${lines} lines`;
    case "file_write":
      return `Wrote ${chars} chars`;
    case "file_patch":
      return `Patched (${lines} lines changed)`;
    case "web_open":
      return summariseWebOpen(raw);
    case "web_scan":
      return summariseWebScan(raw);
    case "web_execute_js":
      return `Ran JS (${chars} chars output)`;
    default:
      return `Returned ${chars} chars (${lines} lines)`;
  }
}

export function extractToolArgument(argsPreview: string, key: string): string {
  const parsed = parseObject(argsPreview);
  const value = parsed?.[key];
  if (typeof value === "string") return value;
  if (value == null) return "";
  return JSON.stringify(value);
}

export function formatCollapsedPreview(raw: string, maxLines = 4): CollapsedPreview {
  if (!raw) return { lines: [], hiddenLines: 0 };
  const lines = raw.replace(/\n$/, "").split("\n");
  return {
    lines: lines.slice(0, maxLines),
    hiddenLines: Math.max(0, lines.length - maxLines),
  };
}

function summariseWebOpen(raw: string): string {
  const payload = parseObject(raw);
  const url = typeof payload?.url === "string" ? payload.url : "";
  if (!url) return "Opened browser tab";
  try {
    const host = new URL(url).host;
    return host ? `Opened browser tab (${host})` : "Opened browser tab";
  } catch {
    return "Opened browser tab";
  }
}

function summariseWebScan(raw: string): string {
  const payload = parseObject(raw);
  if (!payload) return fallbackScanSummary(raw);

  const metadata = asObject(payload.metadata);
  const tabsCount = numberValue(metadata?.tabs_count);
  const content = typeof payload.content === "string" ? payload.content : "";
  const tabSuffix = tabsCount === undefined ? "" : `, ${tabsCount} tab${tabsCount === 1 ? "" : "s"}`;

  if (!content) {
    return tabsCount === undefined ? "Scanned browser" : `Listed ${tabsCount} browser tab${tabsCount === 1 ? "" : "s"}`;
  }

  const mode = looksLikePlainText(content) ? "text" : "page";
  return `Scanned ${mode} (${content.length} chars${tabSuffix})`;
}

function fallbackScanSummary(raw: string): string {
  const lines = raw.split("\n").length;
  return `Scanned page (${raw.length} chars, ${lines} lines)`;
}

function parseObject(raw: string): JsonObject | null {
  try {
    const parsed: unknown = JSON.parse(raw);
    return asObject(parsed);
  } catch {
    return null;
  }
}

function asObject(value: unknown): JsonObject | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as JsonObject)
    : null;
}

function numberValue(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function looksLikePlainText(content: string): boolean {
  return !/<[a-z][\s\S]*>/i.test(content);
}
