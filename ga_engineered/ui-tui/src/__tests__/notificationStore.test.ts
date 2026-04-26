import { describe, expect, it } from "vitest";

import {
  initialNotifications,
  notificationsReducer,
} from "../state/notificationStore.js";

describe("notificationsReducer", () => {
  it("appends a notification on push", () => {
    const after = notificationsReducer(initialNotifications, {
      type: "push",
      level: "info",
      message: "hello",
    });
    expect(after.items).toHaveLength(1);
    expect(after.items[0]?.message).toBe("hello");
  });

  it("dismisses by id", () => {
    let s = notificationsReducer(initialNotifications, {
      type: "push",
      level: "info",
      message: "a",
    });
    const id = s.items[0]?.id ?? "";
    s = notificationsReducer(s, { type: "dismiss", id });
    expect(s.items).toHaveLength(0);
  });

  it("expires items past their TTL", () => {
    const past = notificationsReducer(initialNotifications, {
      type: "push",
      level: "warn",
      message: "x",
      ttl_ms: 10,
    });
    const future = past.items[0]!.expires_at + 1000;
    const after = notificationsReducer(past, { type: "expire", now: future });
    expect(after.items).toHaveLength(0);
  });

  it("keeps items whose TTL has not yet passed", () => {
    const past = notificationsReducer(initialNotifications, {
      type: "push",
      level: "info",
      message: "live",
      ttl_ms: 5000,
    });
    const after = notificationsReducer(past, { type: "expire", now: Date.now() });
    expect(after.items).toHaveLength(1);
  });
});
