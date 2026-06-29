export const env = {
  appName: import.meta.env.VITE_APP_NAME ?? "AgentScope AG-UI Scaffold",
  apiBaseUrl:
    import.meta.env.VITE_API_BASE_URL ??
    import.meta.env.VITE_AGENT_SERVICE_URL ??
    "http://localhost:8000",
};
