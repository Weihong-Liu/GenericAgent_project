import { Text } from "ink";
import React from "react";

import { DialogFrame } from "./dialog.js";
import type { ExtensionSummary } from "../schemas.js";

export interface ExtensionListProps {
  title: string;
  items: readonly ExtensionSummary[];
  accentColor?: string;
  emptyLabel?: string;
}

export function ExtensionList({
  title,
  items,
  accentColor = "cyan",
  emptyLabel = "none discovered",
}: ExtensionListProps): React.ReactElement {
  return (
    <DialogFrame title={title} accentColor={accentColor} instructions="read-only">
      {items.length === 0 ? (
        <Text color="gray" dimColor>
          {emptyLabel}
        </Text>
      ) : (
        <>
          {items.slice(0, 12).map((item) => (
            <Text key={`${item.kind}:${item.source}:${item.name}`}>
              <Text color={item.status === "sample" ? "gray" : accentColor}>
                {item.status}
              </Text>{" "}
              <Text bold>{item.name}</Text>{" "}
              <Text color="gray" dimColor>
                {item.source}
              </Text>
            </Text>
          ))}
          {items.length > 12 ? (
            <Text color="gray" dimColor>
              and {items.length - 12} more
            </Text>
          ) : null}
        </>
      )}
    </DialogFrame>
  );
}
