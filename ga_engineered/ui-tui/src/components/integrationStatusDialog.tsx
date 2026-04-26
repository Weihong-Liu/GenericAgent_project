import { Text } from "ink";
import React from "react";

import { DialogFrame } from "./dialog.js";
import type { IntegrationStatus } from "../schemas.js";

export interface IntegrationStatusDialogProps {
  integrations: readonly IntegrationStatus[];
}

export function IntegrationStatusDialog({
  integrations,
}: IntegrationStatusDialogProps): React.ReactElement {
  return (
    <DialogFrame title="Integrations" accentColor="magenta" instructions="read-only">
      {integrations.length === 0 ? (
        <Text color="gray" dimColor>
          no integrations discovered
        </Text>
      ) : (
        <>
          {integrations.map((item) => (
            <Text key={item.name}>
              <Text color={item.available ? "green" : "yellow"}>{item.status}</Text>{" "}
              <Text bold>{item.label}</Text>{" "}
              <Text color="gray" dimColor>
                {item.detail} - {item.action}
              </Text>
            </Text>
          ))}
        </>
      )}
    </DialogFrame>
  );
}
