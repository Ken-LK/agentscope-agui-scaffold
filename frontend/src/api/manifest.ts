/** Backend manifest contract (see backend/app/api/manifest.py). */

export type AgentProfile = {
  id: string;
  name: string;
  reasoning: boolean;
  tools: string[];
};

export type ToolCatalogEntry = {
  name: string;
  description: string;
  readOnly: boolean;
  enabled: boolean;
};

export type ProtocolCapabilities = {
  reasoning: boolean;
  writeTools: boolean;
  confirm: boolean;
};

export type Manifest = {
  app: { name: string; version: string; environment: string };
  defaultAgentId: string;
  agentProfiles: AgentProfile[];
  suggestions: string[];
  toolCatalog: ToolCatalogEntry[];
  protocolCapabilities: ProtocolCapabilities;
};

/** Safe local fallback used when the manifest request fails. */
export function fallbackManifest(appName = "AgentScope AG-UI Scaffold"): Manifest {
  return {
    app: { name: appName, version: "0.0.0", environment: "unknown" },
    defaultAgentId: "default",
    agentProfiles: [
      { id: "default", name: appName, reasoning: false, tools: [] },
    ],
    suggestions: [],
    toolCatalog: [],
    protocolCapabilities: { reasoning: false, writeTools: false, confirm: true },
  };
}

export function manifestUrl(apiBaseUrl: string): string {
  return `${apiBaseUrl.replace(/\/$/, "")}/api/manifest`;
}

export async function fetchManifest(
  apiBaseUrl: string,
  fetchImpl: typeof fetch = fetch,
): Promise<Manifest> {
  const response = await fetchImpl(manifestUrl(apiBaseUrl), {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`Manifest request failed: HTTP ${response.status}`);
  }
  return (await response.json()) as Manifest;
}
