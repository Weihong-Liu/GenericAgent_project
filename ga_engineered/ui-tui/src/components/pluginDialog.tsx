import React from "react";

import { ExtensionList } from "./extensionList.js";
import type { ExtensionSummary } from "../schemas.js";

export function PluginDialog({
  items,
}: {
  items: readonly ExtensionSummary[];
}): React.ReactElement {
  return (
    <ExtensionList
      title="Plugins"
      items={items}
      accentColor="magenta"
      emptyLabel="no plugins discovered"
    />
  );
}
