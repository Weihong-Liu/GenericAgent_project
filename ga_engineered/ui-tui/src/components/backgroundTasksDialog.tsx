import { Text } from "ink";
import React from "react";

import { DialogFrame } from "./dialog.js";
import type { BackgroundTask } from "../schemas.js";

export interface BackgroundTasksDialogProps {
  tasks: readonly BackgroundTask[];
  busy: boolean;
  loading?: boolean;
}

export function BackgroundTasksDialog({
  tasks,
  busy,
  loading = false,
}: BackgroundTasksDialogProps): React.ReactElement {
  return (
    <DialogFrame
      title="Background Tasks"
      accentColor="yellow"
      instructions="esc closes"
      footer={busy ? "runtime is busy" : "runtime is idle"}
    >
      {loading ? (
        <Text color="gray" dimColor>
          loading tasks...
        </Text>
      ) : tasks.length === 0 ? (
        <Text color="gray" dimColor>
          no background tasks
        </Text>
      ) : (
        <>
          {tasks.map((task) => (
            <Text key={task.id}>
              <Text color={task.status === "running" ? "yellow" : "gray"}>
                {task.status}
              </Text>{" "}
              <Text bold>{task.label}</Text>{" "}
              <Text color="gray" dimColor>
                {task.detail}
              </Text>
            </Text>
          ))}
        </>
      )}
    </DialogFrame>
  );
}
