# 前端生产镜像（F-508）：Node 构建 + Nginx 托管 dist
# 构建上下文必须是仓库根目录，以便复用 nginx/nginx.conf：
#   docker build -f frontend/Dockerfile -t aiinsight-frontend .
FROM node:22-alpine AS build
WORKDIR /app

ARG VITE_API_URL=
ARG VITE_APP_VERSION=1.0.0
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_APP_VERSION=$VITE_APP_VERSION

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx/nginx.conf /etc/nginx/nginx.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD wget -qO- http://127.0.0.1/ >/dev/null || exit 1
