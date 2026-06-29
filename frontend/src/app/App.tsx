import { AuiProvider, Suggestions, useAui } from "@assistant-ui/react";
import { PanelLeft } from "lucide-react";

import { Thread } from "@/components/assistant-ui/thread";
import { ThreadListSidebar } from "@/components/assistant-ui/threadlist-sidebar";
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import { AgentRuntimeProvider } from "@/runtime/AgentRuntimeProvider";
import { ManifestProvider, useManifest } from "@/runtime/ManifestProvider";

function ThreadSurface() {
  const { manifest } = useManifest();
  const aui = useAui({
    suggestions: Suggestions(
      manifest.suggestions.map((prompt) => ({ title: prompt, label: "", prompt })),
    ),
  });

  return (
    <AuiProvider value={aui}>
      <Thread />
    </AuiProvider>
  );
}

function Workbench() {
  const { manifest, status } = useManifest();
  return (
    <AgentRuntimeProvider>
      <SidebarProvider defaultOpen>
        <ThreadListSidebar />
        <SidebarInset className="flex h-dvh min-w-0 flex-col overflow-hidden">
          <header className="flex h-14 shrink-0 items-center gap-3 border-b px-4">
            <SidebarTrigger />
            <div className="bg-primary text-primary-foreground flex size-8 items-center justify-center rounded-lg">
              <PanelLeft className="size-4" />
            </div>
            <div className="min-w-0">
              <h1 className="truncate text-sm font-semibold">
                {manifest.app.name}
              </h1>
              <p className="text-muted-foreground truncate text-xs">
                AG-UI · POST /ag-ui{status === "degraded" ? " (manifest degraded)" : ""}
              </p>
            </div>
          </header>
          <div className="min-h-0 flex-1 overflow-hidden">
            <ThreadSurface />
          </div>
        </SidebarInset>
      </SidebarProvider>
    </AgentRuntimeProvider>
  );
}

export function App() {
  return (
    <ManifestProvider>
      <Workbench />
    </ManifestProvider>
  );
}
