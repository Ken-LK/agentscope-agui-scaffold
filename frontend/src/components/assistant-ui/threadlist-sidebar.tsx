import type * as React from "react";
import { MessagesSquare, ServerCog } from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
} from "@/components/ui/sidebar";
import { ThreadList } from "@/components/assistant-ui/thread-list";
import { useAgentThreadRegistry } from "@/runtime/AgentRuntimeProvider";
import { useManifest } from "@/runtime/ManifestProvider";

function AgentSelector() {
  const { manifest } = useManifest();
  const { agentId, selectAgent } = useAgentThreadRegistry();
  if (manifest.agentProfiles.length <= 1) return null;
  return (
    <div className="px-2 pb-2">
      <label className="text-muted-foreground mb-1 block text-xs font-medium">
        Agent
      </label>
      <select
        className="bg-background w-full rounded-md border px-2 py-1.5 text-sm"
        value={agentId}
        onChange={(event) => selectAgent(event.target.value)}
      >
        {manifest.agentProfiles.map((profile) => (
          <option key={profile.id} value={profile.id}>
            {profile.name}
          </option>
        ))}
      </select>
    </div>
  );
}

export function ThreadListSidebar({
  ...props
}: React.ComponentProps<typeof Sidebar>) {
  return (
    <Sidebar {...props}>
      <SidebarHeader className="aui-sidebar-header mb-2 border-b">
        <div className="aui-sidebar-header-content flex items-center justify-between">
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton size="lg" asChild>
                <a
                  href="https://docs.agentscope.io/zh/v2"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <div className="aui-sidebar-header-icon-wrapper bg-sidebar-primary text-sidebar-primary-foreground flex aspect-square size-8 items-center justify-center rounded-lg">
                    <MessagesSquare className="aui-sidebar-header-icon size-4" />
                  </div>
                  <div className="aui-sidebar-header-heading me-6 flex flex-col gap-0.5 leading-none">
                    <span className="aui-sidebar-header-title font-semibold">
                      AgentScope 2.0
                    </span>
                  </div>
                </a>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </div>
      </SidebarHeader>
      <SidebarContent className="aui-sidebar-content px-2">
        <AgentSelector />
        <ThreadList />
      </SidebarContent>
      <SidebarRail />
      <SidebarFooter className="aui-sidebar-footer border-t">
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" asChild>
              <a
                  href="https://docs.agentscope.io/zh/v2"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                <div className="aui-sidebar-footer-icon-wrapper bg-sidebar-primary text-sidebar-primary-foreground flex aspect-square size-8 items-center justify-center rounded-lg">
                  <ServerCog className="aui-sidebar-footer-icon size-4" />
                </div>
                <div className="aui-sidebar-footer-heading flex flex-col gap-0.5 leading-none">
                  <span className="aui-sidebar-footer-title font-semibold">
                    AG-UI Client
                  </span>
                  <span>Native /ag-ui (AgentScope 2.0)</span>
                </div>
              </a>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  );
}
