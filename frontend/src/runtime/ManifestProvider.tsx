import {
  createContext,
  type ReactNode,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  type Manifest,
  fallbackManifest,
  fetchManifest,
} from "../api/manifest";
import { env } from "../env";

export type ManifestState = {
  manifest: Manifest;
  status: "loading" | "ready" | "degraded";
};

const ManifestContext = createContext<ManifestState | null>(null);

export function useManifest(): ManifestState {
  const value = useContext(ManifestContext);
  if (!value) {
    throw new Error("useManifest must be used inside ManifestProvider");
  }
  return value;
}

type ManifestProviderProps = {
  children: ReactNode;
  /** Test seam: override the fetcher. */
  load?: () => Promise<Manifest>;
};

export function ManifestProvider({ children, load }: ManifestProviderProps) {
  const [state, setState] = useState<ManifestState>({
    manifest: fallbackManifest(env.appName),
    status: "loading",
  });

  useEffect(() => {
    let cancelled = false;
    const loader = load ?? (() => fetchManifest(env.apiBaseUrl));
    loader()
      .then((manifest) => {
        if (!cancelled) setState({ manifest, status: "ready" });
      })
      .catch((error) => {
        // Degrade gracefully: keep the fallback so the workbench still runs
        // against the default /ag-ui endpoint.
        console.error("[manifest] falling back:", error);
        if (!cancelled) {
          setState((prev) => ({ manifest: prev.manifest, status: "degraded" }));
        }
      });
    return () => {
      cancelled = true;
    };
  }, [load]);

  const value = useMemo(() => state, [state]);

  return (
    <ManifestContext.Provider value={value}>
      {children}
    </ManifestContext.Provider>
  );
}
