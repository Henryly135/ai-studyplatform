import { describe, expect, it, vi } from "vitest";

import {
  runScopedCourseChatLoad,
  runScopedCourseChatSend,
} from "./courseChatAsyncScope";

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });

  return { promise, resolve, reject };
}

describe("CourseChatSidebar async scope isolation", () => {
  it("does not apply a late loadSession response after the module changes", async () => {
    const moduleAScope = Symbol("module-a");
    const moduleBScope = Symbol("module-b");
    let activeScope = moduleAScope;
    let visibleSession = "module-b-session";
    const detail = deferred<{ sessionUuid: string }>();
    const onError = vi.fn();
    const onSettled = vi.fn();

    const pendingLoad = runScopedCourseChatLoad({
      load: () => detail.promise,
      isCurrent: () => activeScope === moduleAScope,
      onSuccess: (value) => {
        visibleSession = value.sessionUuid;
      },
      onError,
      onSettled,
    });

    activeScope = moduleBScope;
    detail.resolve({ sessionUuid: "module-a-session" });
    await pendingLoad;

    expect(visibleSession).toBe("module-b-session");
    expect(onError).not.toHaveBeenCalled();
    expect(onSettled).not.toHaveBeenCalled();
  });

  it("does not refresh or apply a late handleSend response after the module changes", async () => {
    const moduleAScope = Symbol("module-a");
    const moduleBScope = Symbol("module-b");
    let activeScope = moduleAScope;
    let visibleReply = "module-b-reply";
    const reply = deferred<{ reply: string }>();
    const refresh = vi.fn(async () => ["module-a-session"]);
    const onError = vi.fn();
    const onSettled = vi.fn();

    const pendingSend = runScopedCourseChatSend({
      send: () => reply.promise,
      refresh,
      isCurrent: () => activeScope === moduleAScope,
      onSuccess: (value) => {
        visibleReply = value.reply;
      },
      onError,
      onSettled,
    });

    activeScope = moduleBScope;
    reply.resolve({ reply: "module-a-reply" });
    await pendingSend;

    expect(visibleReply).toBe("module-b-reply");
    expect(refresh).not.toHaveBeenCalled();
    expect(onError).not.toHaveBeenCalled();
    expect(onSettled).not.toHaveBeenCalled();
  });

  it("does not apply a late session refresh when the module changes after send resolves", async () => {
    const moduleAScope = Symbol("module-a");
    const moduleBScope = Symbol("module-b");
    let activeScope = moduleAScope;
    let visibleSessions = ["module-b-session"];
    const refreshedSessions = deferred<string[]>();
    const refresh = vi.fn(() => refreshedSessions.promise);
    const onError = vi.fn();
    const onSettled = vi.fn();

    const pendingSend = runScopedCourseChatSend({
      send: async () => ({ reply: "module-a-reply" }),
      refresh,
      isCurrent: () => activeScope === moduleAScope,
      onSuccess: (_response, sessions) => {
        visibleSessions = sessions;
      },
      onError,
      onSettled,
    });

    await vi.waitFor(() => expect(refresh).toHaveBeenCalledOnce());
    activeScope = moduleBScope;
    refreshedSessions.resolve(["module-a-session"]);
    await pendingSend;

    expect(visibleSessions).toEqual(["module-b-session"]);
    expect(onError).not.toHaveBeenCalled();
    expect(onSettled).not.toHaveBeenCalled();
  });
});
