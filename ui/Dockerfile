# Stage 1 — build
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

# Stage 2 — serve via nginx
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
# non-root user (nginx:alpine 기본 nginx 사용자 사용 — UID 101)
RUN sed -i 's@listen       80;@listen 8080;@' /etc/nginx/conf.d/default.conf 2>/dev/null || true && \
    chown -R nginx:nginx /usr/share/nginx/html /var/cache/nginx /var/log/nginx /etc/nginx /run && \
    chmod -R g=u /usr/share/nginx/html /var/cache/nginx /var/log/nginx /etc/nginx /run
USER nginx
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
  CMD wget -q -O- http://localhost:8080/healthz || exit 1
CMD ["nginx", "-g", "daemon off;"]
