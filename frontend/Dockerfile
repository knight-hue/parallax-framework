# syntax=docker/dockerfile:1

## Node 版本与开发环境（便携 node v24）保持一致，避免"本地能跑、镜像里不行"。
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

## NEXT_PUBLIC_* 会在构建期被内联进产物，所以必须在 build 阶段传入，运行期再改变量是无效的。
## 默认值指向本机 8000，正好适配 docker compose（api 端口映射到宿主机）。
ARG NEXT_PUBLIC_PARALLAX_API=http://localhost:8000
ENV NEXT_PUBLIC_PARALLAX_API=$NEXT_PUBLIC_PARALLAX_API
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

RUN addgroup -g 1001 -S nodejs && adduser -S nextjs -u 1001

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000

## 用 node 自带的 fetch 探活，镜像里不需要 curl
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:3000/').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["node", "server.js"]
