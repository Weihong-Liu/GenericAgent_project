import { describe, expect, it } from "vitest";

import {
  dequeuePrompt,
  enqueuePrompt,
  initialPromptQueueState,
  promptQueueReducer,
} from "../state/promptQueue.js";

describe("promptQueueReducer", () => {
  it("enqueues trimmed prompts with detected modes", () => {
    const state = enqueuePrompt(initialPromptQueueState, "  !pwd  ");
    expect(state.prompts).toEqual([{ id: 1, text: "!pwd", mode: "bash" }]);
    expect(state.nextId).toBe(2);
  });

  it("ignores empty prompts", () => {
    expect(enqueuePrompt(initialPromptQueueState, "  ")).toBe(initialPromptQueueState);
  });

  it("dequeues in FIFO order", () => {
    const queued = enqueuePrompt(enqueuePrompt(initialPromptQueueState, "first"), "second");
    const first = dequeuePrompt(queued);
    expect(first.prompt?.text).toBe("first");
    const second = dequeuePrompt(first.state);
    expect(second.prompt?.text).toBe("second");
    expect(second.state.prompts).toEqual([]);
  });

  it("removes and clears prompts without resetting id on remove", () => {
    const queued = enqueuePrompt(enqueuePrompt(initialPromptQueueState, "first"), "second");
    const removed = promptQueueReducer(queued, { type: "remove", id: 1 });
    expect(removed.prompts.map((prompt) => prompt.text)).toEqual(["second"]);
    expect(removed.nextId).toBe(3);
    expect(promptQueueReducer(removed, { type: "clear" })).toEqual(initialPromptQueueState);
  });
});
