import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  AssistantRuntimeProvider,
  type ThreadMessage,
} from "@assistant-ui/react";
import { useAgUiRuntime } from "@assistant-ui/react-ag-ui";

import { createAguiHttpAgent } from "../api/agentscopeAgui";
import { env } from "../env";
import { useManifest } from "./ManifestProvider";

type AgentRuntimeProviderProps = {
  children: ReactNode;
};

type StoredThread = {
  id: string;
  messages: readonly ThreadMessage[];
};

export type AgentThreadSummary = {
  id: string;
  title: string;
  updatedAt: number;
};

type AgentThreadRegistry = {
  currentThreadId: string;
  threads: readonly AgentThreadSummary[];
  createThread: () => void;
  deleteThread: (threadId: string) => void;
  switchThread: (threadId: string) => void;
  agentId: string;
  selectAgent: (agentId: string) => void;
};

const AgentThreadRegistryContext =
  createContext<AgentThreadRegistry | null>(null);

export function useAgentThreadRegistry() {
  const registry = useContext(AgentThreadRegistryContext);
  if (!registry) {
    throw new Error(
      "useAgentThreadRegistry must be used inside AgentRuntimeProvider",
    );
  }
  return registry;
}

function getMessageText(message: ThreadMessage): string {
  return message.content
    .map((part) => (part.type === "text" ? part.text : ""))
    .join(" ")
    .trim();
}

function getThreadTitle(messages: readonly ThreadMessage[]): string {
  const firstUserText = messages.find((message) => message.role === "user");
  const title = firstUserText ? getMessageText(firstUserText) : "";
  return title ? title.slice(0, 42) : "New Chat";
}

export function AgentRuntimeProvider({ children }: AgentRuntimeProviderProps) {
  const threadsRef = useRef<Map<string, StoredThread>>(new Map());
  const currentThreadIdRef = useRef("main");
  const [currentThreadId, setCurrentThreadIdState] = useState("main");
  const [threads, setThreads] = useState<readonly AgentThreadSummary[]>([
    { id: "main", title: "New Chat", updatedAt: Date.now() },
  ]);

  if (!threadsRef.current.has("main")) {
    threadsRef.current.set("main", { id: "main", messages: [] });
  }

  const setCurrentThreadId = useCallback((threadId: string) => {
    currentThreadIdRef.current = threadId;
    setCurrentThreadIdState(threadId);
    if (!threadsRef.current.has(threadId)) {
      threadsRef.current.set(threadId, { id: threadId, messages: [] });
    }
  }, []);

  const upsertThreadSummary = useCallback(
    (threadId: string, messages: readonly ThreadMessage[]) => {
      setThreads((previous) => {
        const nextSummary: AgentThreadSummary = {
          id: threadId,
          title: getThreadTitle(messages),
          updatedAt: Date.now(),
        };
        const exists = previous.some((thread) => thread.id === threadId);
        const next = exists
          ? previous.map((thread) =>
              thread.id === threadId ? nextSummary : thread,
            )
          : [nextSummary, ...previous];
        return [...next].sort((left, right) => right.updatedAt - left.updatedAt);
      });
    },
    [],
  );

  const { manifest } = useManifest();
  const [agentId, setAgentId] = useState(manifest.defaultAgentId);
  const agentIdRef = useRef(agentId);

  useEffect(() => {
    agentIdRef.current = agentId;
  }, [agentId]);

  const agent = useMemo(
    () =>
      createAguiHttpAgent({
        apiBaseUrl: env.apiBaseUrl,
        threadId: "main",
        debug: false,
        forwardedProps: () => ({ agentId: agentIdRef.current }),
      }),
    [],
  );

  const selectAgent = useCallback((nextAgentId: string) => {
    setAgentId(nextAgentId);
  }, []);

  const runtime = useAgUiRuntime({
    agent,
    // reasoning is disabled in P0 (frontend schema compatibility risk); keep
    // thinking off until the REASONING_* path is verified end-to-end (P2-T5).
    showThinking: false,
    logger: {
      debug: (...args) => console.debug("[agui]", ...args),
      error: (...args) => console.error("[agui]", ...args),
    },
    onError: (error) => console.error("[agui]", error),
  });

  const persistCurrentThread = useCallback(() => {
    const threadId = currentThreadIdRef.current;
    const messages = runtime.thread.getState().messages;
    threadsRef.current.set(threadId, { id: threadId, messages });
    upsertThreadSummary(threadId, messages);
  }, [runtime, upsertThreadSummary]);

  const switchThread = useCallback(
    (threadId: string) => {
      if (threadId === currentThreadIdRef.current) return;
      persistCurrentThread();
      const thread = threadsRef.current.get(threadId) ?? {
        id: threadId,
        messages: [],
      };
      threadsRef.current.set(threadId, thread);
      setCurrentThreadId(threadId);
      runtime.thread.reset(thread.messages);
    },
    [persistCurrentThread, runtime, setCurrentThreadId],
  );

  const createThread = useCallback(() => {
    persistCurrentThread();
    const threadId = crypto.randomUUID();
    threadsRef.current.set(threadId, { id: threadId, messages: [] });
    setThreads((previous) => [
      { id: threadId, title: "New Chat", updatedAt: Date.now() },
      ...previous,
    ]);
    setCurrentThreadId(threadId);
    runtime.thread.reset([]);
  }, [persistCurrentThread, runtime, setCurrentThreadId]);

  const deleteThread = useCallback(
    (threadId: string) => {
      if (threadsRef.current.size <= 1) return;
      threadsRef.current.delete(threadId);
      setThreads((previous) =>
        previous.filter((thread) => thread.id !== threadId),
      );
      if (threadId !== currentThreadIdRef.current) return;

      const nextThread = [...threadsRef.current.values()][0] ?? {
        id: "main",
        messages: [],
      };
      threadsRef.current.set(nextThread.id, nextThread);
      setCurrentThreadId(nextThread.id);
      runtime.thread.reset(nextThread.messages);
    },
    [runtime, setCurrentThreadId],
  );

  useEffect(() => {
    return runtime.thread.subscribe(() => {
      const threadId = currentThreadIdRef.current;
      const messages = runtime.thread.getState().messages;
      threadsRef.current.set(threadId, { id: threadId, messages });
      upsertThreadSummary(threadId, messages);
    });
  }, [runtime, upsertThreadSummary]);

  const threadRegistry = useMemo<AgentThreadRegistry>(
    () => ({
      currentThreadId,
      threads,
      createThread,
      deleteThread,
      switchThread,
      agentId,
      selectAgent,
    }),
    [
      agentId,
      createThread,
      currentThreadId,
      deleteThread,
      selectAgent,
      switchThread,
      threads,
    ],
  );

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <AgentThreadRegistryContext.Provider value={threadRegistry}>
        {children}
      </AgentThreadRegistryContext.Provider>
    </AssistantRuntimeProvider>
  );
}
