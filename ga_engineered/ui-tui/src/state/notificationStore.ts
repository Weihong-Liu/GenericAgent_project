/**
 * Lightweight toast notifications.
 *
 * Each notification has a TTL after which the parent should remove it.
 * The reducer is purely additive — append on push, filter on expire —
 * so the parent can run a cheap setInterval to GC by ID without race
 * conditions.
 */

export type NotificationLevel = "info" | "success" | "warn" | "error";

export interface Notification {
  id: string;
  level: NotificationLevel;
  message: string;
  /** Wall-clock ms after which the notification should be dropped. */
  expires_at: number;
}

let counter = 0;
const nextId = (): string => `n${++counter}`;

export interface NotificationsState {
  items: Notification[];
}

export type NotificationAction =
  | { type: "push"; level: NotificationLevel; message: string; ttl_ms?: number }
  | { type: "expire"; now: number }
  | { type: "dismiss"; id: string };

export const initialNotifications: NotificationsState = { items: [] };

const DEFAULT_TTL = 3000;

export function notificationsReducer(
  state: NotificationsState,
  action: NotificationAction,
): NotificationsState {
  switch (action.type) {
    case "push": {
      const ttl = action.ttl_ms ?? DEFAULT_TTL;
      const item: Notification = {
        id: nextId(),
        level: action.level,
        message: action.message,
        expires_at: Date.now() + ttl,
      };
      return { items: [...state.items, item] };
    }
    case "expire":
      return { items: state.items.filter((item) => item.expires_at > action.now) };
    case "dismiss":
      return { items: state.items.filter((item) => item.id !== action.id) };
  }
}
