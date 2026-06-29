import { HttpAgent, type HttpAgentConfig } from "@ag-ui/client";

/**
 * Thin factory for the standard AG-UI HTTP agent.
 *
 * The backend exposes the native AgentScope 2.0 `POST /ag-ui` endpoint that
 * speaks standard AG-UI `RunAgentInput`, so the frontend uses the stock
 * `@ag-ui/client` `HttpAgent` with no payload rewriting. Agent profile
 * selection (P2) is carried through standard `forwardedProps.agentId`.
 */
export type CreateAguiHttpAgentOptions = {
  apiBaseUrl: string;
  threadId?: string;
  headers?: Record<string, string>;
  fetch?: HttpAgentConfig["fetch"];
  debug?: boolean;
  forwardedProps?: Record<string, unknown> | (() => Record<string, unknown>);
};

export function aguiUrl(apiBaseUrl: string): string {
  return `${apiBaseUrl.replace(/\/$/, "")}/ag-ui`;
}

export function createAguiHttpAgent(
  options: CreateAguiHttpAgentOptions,
): HttpAgent {
  const agent = new HttpAgent({
    url: aguiUrl(options.apiBaseUrl),
    threadId: options.threadId,
    headers: options.headers,
    // Wrap fetch so it keeps its `window` binding — HttpAgent calls
    // `this.fetch(...)`, and passing the bare `window.fetch` would throw
    // "Illegal invocation".
    fetch:
      options.fetch ??
      ((input: RequestInfo | URL, init?: RequestInit) => fetch(input, init)),
    debug: options.debug ?? false,
  });
  if (options.forwardedProps) {
    installForwardedProps(agent, options.forwardedProps);
  }
  return agent;
}

function installForwardedProps(
  agent: HttpAgent,
  forwardedProps: NonNullable<CreateAguiHttpAgentOptions["forwardedProps"]>,
) {
  const target = agent as unknown as {
    prepareRunAgentInput: (params?: {
      forwardedProps?: Record<string, unknown>;
    }) => { forwardedProps?: Record<string, unknown> };
  };
  const original = target.prepareRunAgentInput;
  target.prepareRunAgentInput = function (params) {
    const input = original.call(this, params);
    const next =
      typeof forwardedProps === "function" ? forwardedProps() : forwardedProps;
    return {
      ...input,
      forwardedProps: {
        ...(input.forwardedProps ?? {}),
        ...next,
      },
    };
  };
}
