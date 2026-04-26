import { Text } from "ink";
import React from "react";

import { DialogFrame } from "./dialog.js";
import type { WorktreeStatusResult } from "../schemas.js";

export interface WorktreeDialogProps {
  status: WorktreeStatusResult | null;
  loading?: boolean;
}

export function WorktreeDialog({
  status,
  loading = false,
}: WorktreeDialogProps): React.ReactElement {
  return (
    <DialogFrame title="Worktree" accentColor="green" instructions="esc closes">
      {loading ? (
        <Text color="gray" dimColor>
          loading worktree...
        </Text>
      ) : !status || !status.is_git ? (
        <Text color="gray" dimColor>
          current workspace is not a git worktree
        </Text>
      ) : (
        <>
          <Text>
            <Text color="gray">path </Text>
            {status.path}
          </Text>
          <Text>
            <Text color="gray">branch </Text>
            {status.branch || "(detached)"}
          </Text>
          <Text>
            <Text color="gray">dirty </Text>
            <Text color={status.dirty ? "yellow" : "green"}>
              {status.dirty ? `${status.changes} changes` : "clean"}
            </Text>
          </Text>
          <Text>
            <Text color="gray">remote </Text>+{status.ahead} / -{status.behind}
          </Text>
        </>
      )}
    </DialogFrame>
  );
}
