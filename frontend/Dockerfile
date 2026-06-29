# AgentScope AG-UI frontend: build static assets, serve them with nginx.
FROM node:22-slim AS build

WORKDIR /app
RUN corepack enable

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .
# VITE_API_BASE_URL can be baked at build time, or proxied at the edge.
ARG VITE_API_BASE_URL
RUN pnpm build

FROM nginx:1.27-alpine AS serve
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
