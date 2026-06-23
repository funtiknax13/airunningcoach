FROM node:22-alpine AS builder
WORKDIR /app
COPY frontend-v2/package*.json ./
RUN npm ci
COPY frontend-v2/ .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /frontend-v2-dist /usr/share/nginx/html
