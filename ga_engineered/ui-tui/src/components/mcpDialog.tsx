import React from "react";

import { ExtensionList } from "./extensionList.js";
import type { ExtensionSummary } from "../schemas.js";

export function McpDialog({
  items,
}: {
  items: readonly ExtensionSummary[];
}): React.ReactElement {
  return (
    <ExtensionList
      title="MCP Servers"
      items={items}
      accentColor="cyan"
      emptyLabel="no MCP servers configured"
    />
  );
}
