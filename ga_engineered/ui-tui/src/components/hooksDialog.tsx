import React from "react";

import { ExtensionList } from "./extensionList.js";
import type { ExtensionSummary } from "../schemas.js";

export function HooksDialog({
  items,
}: {
  items: readonly ExtensionSummary[];
}): React.ReactElement {
  return (
    <ExtensionList
      title="Hooks"
      items={items}
      accentColor="yellow"
      emptyLabel="no hooks discovered"
    />
  );
}
