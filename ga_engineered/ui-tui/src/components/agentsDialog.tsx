import React from "react";

import { ExtensionList } from "./extensionList.js";
import type { ExtensionSummary } from "../schemas.js";

export function AgentsDialog({
  items,
}: {
  items: readonly ExtensionSummary[];
}): React.ReactElement {
  return (
    <ExtensionList
      title="Agents"
      items={items}
      accentColor="green"
      emptyLabel="no custom agents discovered"
    />
  );
}
