import { afterEach, describe, expect, it } from "vitest";

import { defaultHistoryPath } from "../persistence/historyFile.js";

const ENV_KEYS = [
  "GENERIC_AGENT_CONFIG_DIR",
  "GA_CONFIG_DIR",
  "GENERIC_AGENT_HOME",
  "CLAUDE_CONFIG_DIR",
  "HOME",
] as const;

const originalEnv = Object.fromEntries(
  ENV_KEYS.map((key) => [key, process.env[key]]),
) as Record<(typeof ENV_KEYS)[number], string | undefined>;

function resetEnv(): void {
  for (const key of ENV_KEYS) {
    const value = originalEnv[key];
    if (value === undefined) delete process.env[key];
    else process.env[key] = value;
  }
}

afterEach(() => {
  resetEnv();
});

describe("defaultHistoryPath", () => {
  it("prefers GenericAgent config dir aliases before legacy/free-code fallbacks", () => {
    process.env["GENERIC_AGENT_CONFIG_DIR"] = "/tmp/ga-config";
    process.env["GA_CONFIG_DIR"] = "/tmp/ga-short";
    process.env["GENERIC_AGENT_HOME"] = "/tmp/ga-home";
    process.env["CLAUDE_CONFIG_DIR"] = "/tmp/claude-config";

    expect(defaultHistoryPath()).toBe("/tmp/ga-config/history.jsonl");
  });

  it("accepts CLAUDE_CONFIG_DIR as a compatibility fallback", () => {
    delete process.env["GENERIC_AGENT_CONFIG_DIR"];
    delete process.env["GA_CONFIG_DIR"];
    delete process.env["GENERIC_AGENT_HOME"];
    process.env["CLAUDE_CONFIG_DIR"] = "/tmp/free-code-style";

    expect(defaultHistoryPath()).toBe("/tmp/free-code-style/history.jsonl");
  });
});
