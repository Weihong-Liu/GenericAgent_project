import { describe, expect, it } from "vitest";

import { buildRateLimitOptions } from "../components/rateLimitOptions.js";
import type { RuntimeStatus } from "../schemas.js";

describe("buildRateLimitOptions", () => {
  it("includes general recovery options without runtime status", () => {
    const labels = buildRateLimitOptions(null).map((option) => option.label);
    expect(labels).toContain("Compact context");
    expect(labels).toContain("Switch model/provider");
  });

  it("surfaces token budget and Codex auth actions when available", () => {
    const options = buildRateLimitOptions({
      protocol_version: "1.0",
      gateway_version: "0.1.0",
      provider: "openai-codex",
      model: "gpt-5.5",
      session_id: "default",
      turn_count: 2,
      max_turns: 8,
      tokens_used: 900,
      tokens_budget: 1000,
      tool_count: 4,
      skill_count: 1,
      busy: false,
      bridge_running: false,
    });
    expect(options[0]?.label).toBe("Current token budget");
    expect(options.map((option) => option.label)).toContain("Refresh auth");
  });
});
