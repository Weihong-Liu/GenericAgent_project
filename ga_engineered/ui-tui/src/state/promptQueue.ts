import { detectMode, type InputMode } from "./modeDetector.js";

export interface QueuedPrompt {
  id: number;
  text: string;
  mode: InputMode;
}

export interface PromptQueueState {
  prompts: readonly QueuedPrompt[];
  nextId: number;
}

export type PromptQueueAction =
  | { type: "enqueue"; text: string; mode?: InputMode }
  | { type: "dequeue" }
  | { type: "remove"; id: number }
  | { type: "clear" };

export const initialPromptQueueState: PromptQueueState = {
  prompts: [],
  nextId: 1,
};

export function promptQueueReducer(
  state: PromptQueueState,
  action: PromptQueueAction,
): PromptQueueState {
  switch (action.type) {
    case "enqueue": {
      const text = action.text.trim();
      if (!text) return state;
      const prompt: QueuedPrompt = {
        id: state.nextId,
        text,
        mode: action.mode ?? detectMode(text),
      };
      return {
        prompts: [...state.prompts, prompt],
        nextId: state.nextId + 1,
      };
    }
    case "dequeue":
      return {
        prompts: state.prompts.slice(1),
        nextId: state.nextId,
      };
    case "remove":
      return {
        prompts: state.prompts.filter((prompt) => prompt.id !== action.id),
        nextId: state.nextId,
      };
    case "clear":
      return initialPromptQueueState;
  }
}

export function enqueuePrompt(
  state: PromptQueueState,
  text: string,
  mode?: InputMode,
): PromptQueueState {
  return promptQueueReducer(state, {
    type: "enqueue",
    text,
    ...(mode ? { mode } : {}),
  });
}

export function dequeuePrompt(state: PromptQueueState): {
  state: PromptQueueState;
  prompt: QueuedPrompt | null;
} {
  return {
    state: promptQueueReducer(state, { type: "dequeue" }),
    prompt: state.prompts[0] ?? null,
  };
}
