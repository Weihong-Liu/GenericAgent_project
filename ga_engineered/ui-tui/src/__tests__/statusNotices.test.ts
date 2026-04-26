import { describe, expect, it } from "vitest";

import { buildStatusNotices } from "../components/statusNotices.js";
import type { RuntimeStatus } from "../schemas.js";

const BASE_STATUS: RuntimeStatus = {
  protocol_version: "1.0",
  gateway_version: "0.1.0",
  provider: "openai",
  model: "gpt-5.4",
  session_id: "default",
  turn_count: 0,
  max_turns: 8,
  tokens_used: 0,
  tokens_budget: null,
  tool_count: 3,
  skill_count: 0,
  busy: false,
  bridge_running: true,
};

describe("buildStatusNotices", () => {
  it("reports first-turn onboarding and respects dismissals", () => {
    const notices = buildStatusNotices(BASE_STATUS);
    expect(notices.map((notice) => notice.id)).toContain("first-turn");

    const dismissed = buildStatusNotices(BASE_STATUS, new Set(["first-turn"]));
    expect(dismissed.map((notice) => notice.id)).not.toContain("first-turn");
  });

  it("warns when bridge is disconnected", () => {
    const notices = buildStatusNotices({ ...BASE_STATUS, bridge_running: false });
    expect(notices.map((notice) => notice.id)).toContain("browser-bridge");
  });

  it("escalates token budget pressure", () => {
    const warning = buildStatusNotices({
      ...BASE_STATUS,
      tokens_used: 80,
      tokens_budget: 100,
    });
    expect(warning.map((notice) => notice.id)).toContain("token-budget-warning");

    const critical = buildStatusNotices({
      ...BASE_STATUS,
      tokens_used: 95,
      tokens_budget: 100,
    });
    expect(critical.map((notice) => notice.id)).toContain("token-budget-critical");
  });
});
