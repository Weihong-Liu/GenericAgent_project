/**
 * Toast notifications. Renders a small column above the input box;
 * the parent's setInterval drops expired entries.
 */

import { Box, Text } from "ink";
import React from "react";

import type { Notification } from "../state/notificationStore.js";

const COLOR: Record<Notification["level"], string> = {
  info: "cyan",
  success: "green",
  warn: "yellow",
  error: "red",
};

const ICON: Record<Notification["level"], string> = {
  info: "ℹ",
  success: "✓",
  warn: "⚠",
  error: "✗",
};

export function Notifications({
  items,
}: {
  items: readonly Notification[];
}): React.ReactElement | null {
  if (items.length === 0) return null;
  return (
    <Box flexDirection="column" marginTop={1}>
      {items.map((item) => (
        <Text key={item.id} color={COLOR[item.level]}>
          {ICON[item.level]} {item.message}
        </Text>
      ))}
    </Box>
  );
}
